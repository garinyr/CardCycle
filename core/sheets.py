"""core/sheets.py — gspread client + Cards/Config/Transactions access.

Reads the full credential from the `GOOGLE_CREDENTIALS_JSON` env var (not a
file path), then `Credentials.from_service_account_info`.
"""

import json
import os
import re
import time

import gspread
from google.oauth2.service_account import Credentials

from api.config import (
    SCOPES,
    SHEET_CARDS,
    SHEET_CONFIG,
    SHEET_TRANSACTIONS,
    SPREADSHEET_ID,
    TRANSACTIONS_HEADERS,
)

_CACHE_TTL = 300  # 5 minutes

_client: gspread.Client | None = None
_cards_cache: list[dict] | None = None
_cards_cache_ts = 0.0
_config_cache: dict[str, str] | None = None
_config_cache_ts = 0.0


def get_client() -> gspread.Client:
    """gspread client (lazy singleton), credential from `GOOGLE_CREDENTIALS_JSON` env."""
    global _client
    if _client is None:
        raw = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
        if not raw.strip():
            raise RuntimeError("GOOGLE_CREDENTIALS_JSON is not set")
        info = json.loads(raw)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        _client = gspread.authorize(creds)
    return _client


def _worksheet(title: str):
    sh = get_client().open_by_key(SPREADSHEET_ID)
    return sh.worksheet(title)


# --- coercion helpers (get_all_records returns raw cell values) ---

def _to_str(v) -> str:
    return "" if v is None else str(v)


def _to_int(v) -> int | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    s = re.sub(r"[^\d-]", "", str(v))
    if not s or s == "-":
        return None
    return int(s)


def _to_bool(v) -> bool:
    if v is None or v == "":
        return False
    if isinstance(v, bool):
        return v
    return str(v).strip().upper() in ("TRUE", "1", "YES", "Y")


def _coerce_card(r: dict) -> dict:
    return {
        "card_id": _to_int(r.get("card_id")),
        "card_name": _to_str(r.get("card_name")),
        "bank": _to_str(r.get("bank")),
        "card_limit": _to_int(r.get("card_limit")),
        "cutoff_day": _to_int(r.get("cutoff_day")),
        "due_day": _to_int(r.get("due_day")),
        "is_active": _to_bool(r.get("is_active")),
        "created_at": _to_str(r.get("created_at")),
        "updated_at": _to_str(r.get("updated_at")),
    }


def _coerce_tx(r: dict) -> dict:
    return {
        "id": _to_int(r.get("id")),
        "card_id": _to_int(r.get("card_id")),
        "date": _to_str(r.get("date")),
        "amount": _to_int(r.get("amount")),
        "description": _to_str(r.get("description")),
        "category": _to_str(r.get("category")),
        "deleted": _to_bool(r.get("deleted")),
        "input_at": _to_str(r.get("input_at")),
    }


# --- Cards ---

def get_cards(force: bool = False) -> list[dict]:
    global _cards_cache, _cards_cache_ts
    now = time.time()
    if not force and _cards_cache is not None and now - _cards_cache_ts < _CACHE_TTL:
        return _cards_cache
    ws = _worksheet(SHEET_CARDS)
    _cards_cache = [_coerce_card(r) for r in ws.get_all_records()]
    _cards_cache_ts = now
    return _cards_cache


def get_card(card_id: int) -> dict | None:
    for c in get_cards():
        if c["card_id"] == card_id:
            return c
    return None


def _invalidate_cards_cache() -> None:
    global _cards_cache
    _cards_cache = None


def update_card_limit(card_id: int, new_limit) -> None:
    ws = _worksheet(SHEET_CARDS)
    ids = ws.col_values(1)
    for idx, v in enumerate(ids):
        if _to_int(v) == card_id:
            row = idx + 1
            break
    else:
        raise RuntimeError(f"card_id {card_id} not found")
    ws.update_cell(row, 4, new_limit)  # column D = card_limit
    _invalidate_cards_cache()


# --- Config ---

def get_config(force: bool = False) -> dict[str, str]:
    global _config_cache, _config_cache_ts
    now = time.time()
    if not force and _config_cache is not None and now - _config_cache_ts < _CACHE_TTL:
        return _config_cache
    ws = _worksheet(SHEET_CONFIG)
    d: dict[str, str] = {}
    for r in ws.get_all_records():
        k = _to_str(r.get("key")).strip()
        if k:
            d[k] = _to_str(r.get("value"))
    _config_cache = d
    _config_cache_ts = now
    return _config_cache


def _invalidate_config_cache() -> None:
    global _config_cache
    _config_cache = None


def set_config(key: str, value) -> None:
    ws = _worksheet(SHEET_CONFIG)
    keys = ws.col_values(1)  # column A = key
    try:
        idx = keys.index(key)
    except ValueError:
        raise RuntimeError(f"Config has no key '{key}'")
    row = idx + 1
    ws.update_cell(row, 2, value)
    _invalidate_config_cache()


def allocate_ids(count: int = 1) -> int:
    """Reserve `count` monotonic ids in one update; return the first id."""
    ws = _worksheet(SHEET_CONFIG)
    keys = ws.col_values(1)
    try:
        idx = keys.index("next_id")
    except ValueError:
        raise RuntimeError("Config has no key 'next_id'")
    row = idx + 1
    cur = _to_int(ws.cell(row, 2).value) or 0
    ws.update_cell(row, 2, cur + count)
    _invalidate_config_cache()
    return cur


def get_default_card() -> dict | None:
    cfg = get_config()
    default_id = _to_int(cfg.get("default_card_id"))
    if default_id is not None:
        card = get_card(default_id)
        if card:
            return card
    for c in get_cards():
        if c["is_active"]:
            return c
    return None


# --- Transactions ---

def read_transactions() -> list[dict]:
    ws = _worksheet(SHEET_TRANSACTIONS)
    return [_coerce_tx(r) for r in ws.get_all_records()]


def append_transactions(rows: list[dict]) -> None:
    if not rows:
        return
    ws = _worksheet(SHEET_TRANSACTIONS)
    values = []
    for r in rows:
        values.append([
            r.get("id", ""),
            r.get("card_id", ""),
            r.get("date", ""),
            r.get("amount", ""),
            r.get("description", ""),
            r.get("category", ""),
            "TRUE" if r.get("deleted") else "FALSE",
            r.get("input_at", ""),
        ])
    # column order must match TRANSACTIONS_HEADERS
    assert TRANSACTIONS_HEADERS[0] == "id"
    # RAW: "YYYY-MM-DD" & "TRUE"/"FALSE" stay strings, not parsed by Sheets
    # (USER_ENTERED would turn dates into "8/23/2026" → fromisoformat crash)
    ws.append_rows(values, value_input_option="RAW")
