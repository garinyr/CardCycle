"""core/pending.py — reply-free pending context for card input flows.

Single source of truth for the "waiting for a typed answer" state (plan:
`docs/card-cycle/plan/card-input-no-reply.md`). Config keys owned here:

- `cards.pending_action` — add | limit | cutoff | ""
- `cards.pending_ts` — when it was set (ISO WIB)
- `cards.edit_card_id` — target card for limit/cutoff
- draft keys (cards.draft_*) — parsed Add values awaiting confirmation

Rules: set_pending overwrites any previous pending; pending() reads and
auto-clears when stale (> PENDING_TTL_S); clear_pending empties everything.
Only the typed answer for the action that created the state may consume it —
every other route exits or replaces it (see webhook routing).
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from api.config import (
    CONFIG_CARDS_EDIT_CARD_ID,
    CONFIG_DRAFT_AMOUNT,
    CONFIG_DRAFT_CUTOFF,
    CONFIG_DRAFT_NAME,
    CONFIG_PENDING_ACTION,
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
PENDING_TTL_S = 300  # D2: 5 minutes

_ALL_KEYS = (
    CONFIG_PENDING_ACTION,
    CONFIG_PENDING_TS,
    CONFIG_CARDS_EDIT_CARD_ID,
    CONFIG_DRAFT_NAME,
    CONFIG_DRAFT_AMOUNT,
    CONFIG_DRAFT_CUTOFF,
)


def _now() -> datetime:
    return datetime.now(TZ)


def _set(key: str, value) -> None:
    sheets.upsert_config(key, value)


def set_pending(action: str, card_id: int | None = None) -> None:
    """Record that we are waiting for a typed answer for `action`."""
    _set(CONFIG_PENDING_ACTION, action)
    _set(CONFIG_PENDING_TS, _now().isoformat(timespec="seconds"))
    _set(CONFIG_CARDS_EDIT_CARD_ID, str(card_id) if card_id is not None else "")
    log_event(log, "pending_set", action=action, card=card_id)


def clear_pending() -> None:
    """Empty the pending state. No-op (no writes) when nothing is pending, so
    route guards can call it freely without touching the sheet."""
    cfg = sheets.get_config() or {}
    if not any(str(cfg.get(k, "")).strip() for k in _ALL_KEYS):
        return
    log_event(log, "pending_clear")
    for key in _ALL_KEYS:
        _set(key, "")


def pending() -> tuple[str, int | None] | None:
    """Return (action, card_id) when a fresh pending exists, else None.

    A stale pending (> PENDING_TTL_S) is cleared first and returns None, so
    an abandoned action can never capture unrelated text later.
    """
    cfg = sheets.get_config() or {}
    action = str(cfg.get(CONFIG_PENDING_ACTION, "")).strip()
    if not action:
        return None
    raw_ts = str(cfg.get(CONFIG_PENDING_TS, "")).strip()
    try:
        ts = datetime.fromisoformat(raw_ts).astimezone(TZ)
    except ValueError:
        clear_pending()
        return None
    if _now() - ts > timedelta(seconds=PENDING_TTL_S):
        log_event(log, "pending_stale", action=action, ttl_s=PENDING_TTL_S)
        clear_pending()
        return None
    raw_card = str(cfg.get(CONFIG_CARDS_EDIT_CARD_ID, "")).strip()
    card_id = None
    if raw_card:
        try:
            card_id = int(raw_card)
        except ValueError:
            card_id = None
    return action, card_id


# --- draft helpers (Add confirmation) ---

def save_draft(name: str, amount: int, cutoff: int) -> None:
    _set(CONFIG_DRAFT_NAME, name)
    _set(CONFIG_DRAFT_AMOUNT, str(amount))
    _set(CONFIG_DRAFT_CUTOFF, str(cutoff))


def draft() -> tuple[str, int, int] | None:
    cfg = sheets.get_config() or {}
    name = str(cfg.get(CONFIG_DRAFT_NAME, "")).strip()
    if not name:
        return None
    try:
        return name, int(cfg.get(CONFIG_DRAFT_AMOUNT) or 0), int(cfg.get(CONFIG_DRAFT_CUTOFF) or 13)
    except (TypeError, ValueError):
        return None
