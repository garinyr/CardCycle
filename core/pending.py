"""core/pending.py — reply-free pending context (single JSON state, app-wide).

All transient bot state (waiting-for-input context) lives in ONE Config row
`app.pending` as a compact JSON string — instead of many per-key rows — so a
set/clear costs one write and one read.

JSON shape:
    {"a": action, "c": card_id|null, "o": origin, "t": iso_ts, "d": {draft}}

Legacy read fallback: if the new key is absent, old rows (`app.pending_action`,
`app.pending_ts`, `app.edit_card_id`, `app.pending_origin`, `app.draft_*`) are
still honoured during migration; clearing removes both.
"""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from api.config import (
    CONFIG_CARDS_EDIT_CARD_ID,
    CONFIG_DRAFT_AMOUNT,
    CONFIG_DRAFT_CUTOFF,
    CONFIG_DRAFT_NAME,
    CONFIG_PENDING_ACTION,
    CONFIG_PENDING_ORIGIN,
    CONFIG_PENDING_STATE,
    CONFIG_PENDING_TS,
)
from core.cb import (  # single source
    CARDS_ACTION_ADD as ACTION_ADD,
    CARDS_ACTION_CUTOFF as ACTION_CUTOFF,
    CARDS_ACTION_LIMIT as ACTION_LIMIT,
)
from core import sheets
from core.logger import get_logger, log_event

log = get_logger("pending")

TZ = ZoneInfo("Asia/Jakarta")
PENDING_TTL_S = 300  # 5 minutes

ORIGIN_LIST = "list"
ORIGIN_CARD = "card"
ORIGIN_STMT = "stmt"
ORIGIN_RUN = "run"

ACTION_EXPENSE = "expense"
ACTION_MONTH = "month"

# Legacy rows cleaned on clear when still present (migration).
_LEGACY_KEYS = (
    CONFIG_PENDING_ACTION,
    CONFIG_PENDING_ORIGIN,
    CONFIG_PENDING_TS,
    CONFIG_CARDS_EDIT_CARD_ID,
    CONFIG_DRAFT_NAME,
    CONFIG_DRAFT_AMOUNT,
    CONFIG_DRAFT_CUTOFF,
)


def _now() -> datetime:
    return datetime.now(TZ)


def _dump(a: str, c: int | None, o: str, t: str, d: dict | None) -> str:
    return json.dumps({"a": a, "c": c, "o": o, "t": t, "d": d or {}}, ensure_ascii=False)


def _load(raw: str) -> dict:
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def set_pending(action: str, card_id: int | None = None, origin: str | None = None) -> None:
    """Record that we are waiting for a typed answer for `action` (one write)."""
    origin = origin or ORIGIN_LIST
    sheets.upsert_config(CONFIG_PENDING_STATE,
                         _dump(action, card_id, origin, _now().isoformat(timespec="seconds"), None))
    log_event(log, "pending_set", action=action, card=card_id, origin=origin)


def clear_pending() -> None:
    """Empty the pending state. Writes only when something is pending."""
    cfg = sheets.get_config() or {}
    if str(cfg.get(CONFIG_PENDING_STATE, "")).strip() or any(
            str(cfg.get(k, "")).strip() for k in _LEGACY_KEYS):
        sheets.upsert_config(CONFIG_PENDING_STATE, "")
        for k in _LEGACY_KEYS:  # migration: tidy old rows if still present
            if str(cfg.get(k, "")).strip():
                sheets.upsert_config(k, "")
        log_event(log, "pending_clear")


def read_pending() -> tuple[str, str, int | None, str] | None:
    """(kind, action, card_id, origin): fresh | stale, or None when empty."""
    cfg = sheets.get_config() or {}
    raw = str(cfg.get(CONFIG_PENDING_STATE, "")).strip()
    if raw:
        data = _load(raw)
        action = str(data.get("a", "")).strip()
        if not action:
            return None
        origin = str(data.get("o", "")).strip() or ORIGIN_LIST
        c = data.get("c")
        try:
            card_id = int(c) if c not in (None, "") else None
        except (TypeError, ValueError):
            card_id = None
        ts = _parse_ts(str(data.get("t", "")).strip())
        if ts is None or _now() - ts > timedelta(seconds=PENDING_TTL_S):
            return "stale", action, card_id, origin
        return "fresh", action, card_id, origin
    # Legacy fallback (migration period)
    action = str(cfg.get(CONFIG_PENDING_ACTION, "")).strip()
    if not action:
        return None
    origin = str(cfg.get(CONFIG_PENDING_ORIGIN, "")).strip() or ORIGIN_LIST
    raw_card = str(cfg.get(CONFIG_CARDS_EDIT_CARD_ID, "")).strip()
    try:
        card_id = int(raw_card) if raw_card else None
    except ValueError:
        card_id = None
    ts = _parse_ts(str(cfg.get(CONFIG_PENDING_TS, "")).strip())
    if ts is None or _now() - ts > timedelta(seconds=PENDING_TTL_S):
        return "stale", action, card_id, origin
    return "fresh", action, card_id, origin


def pending() -> tuple[str, int | None] | None:
    """Fresh pending as (action, card_id), else None."""
    state = read_pending()
    if state and state[0] == "fresh":
        return state[1], state[2]
    return None


def _parse_ts(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).astimezone(TZ)
    except ValueError:
        return None


# --- draft helpers (Add confirmation) ---

def save_draft(name: str, amount: int, cutoff: int) -> None:
    """Attach a draft to the current pending state (single write)."""
    cfg = sheets.get_config() or {}
    data = _load(str(cfg.get(CONFIG_PENDING_STATE, "")))
    data["d"] = {"n": name, "m": amount, "x": cutoff}
    sheets.upsert_config(CONFIG_PENDING_STATE, json.dumps(data, ensure_ascii=False))


def draft() -> tuple[str, int, int] | None:
    cfg = sheets.get_config() or {}
    data = _load(str(cfg.get(CONFIG_PENDING_STATE, ""))).get("d") or {}
    name = str(data.get("n", "")).strip()
    if not name:
        return None
    try:
        return name, int(data.get("m", 0)), int(data.get("x", 13))
    except (TypeError, ValueError):
        return None
