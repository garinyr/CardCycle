"""tests/test_pending_input.py — reply-free card input (core.pending + routing).

Covers: pending set/read/clear + stale expiry; free-text consumption in
`_route` (limit value); guards that clear pending when the user taps another
menu button / slash / cancel.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import api.webhook as w
from core import menu, pending
from core import prompts

TZ = ZoneInfo("Asia/Jakarta")
BNI = {"card_id": 1, "card_name": "BNI Mastercard", "bank": "BNI", "card_limit": 15000000, "cutoff_day": 13, "is_active": True}
TOKOPEDIA = {"card_id": 2, "card_name": "Tokopedia Card", "bank": "Tokopedia", "card_limit": 8000000, "cutoff_day": 27, "is_active": True}


def _patch_cfg(monkeypatch, cfg):
    upserts = []

    def _upsert(k, v):
        cfg[k] = v
        upserts.append((k, v))

    monkeypatch.setattr("core.sheets.get_config", lambda: cfg)
    monkeypatch.setattr("core.sheets.upsert_config", _upsert)
    return upserts


def _iso(offset_minutes=0):
    return (datetime.now(TZ) + timedelta(minutes=offset_minutes)).isoformat(timespec="seconds")


# --- core.pending unit ---

def test_set_and_read_pending(monkeypatch):
    cfg = {}
    _patch_cfg(monkeypatch, cfg)
    pending.set_pending("limit", 2)
    assert pending.pending() == ("limit", 2)


def test_pending_none_when_empty(monkeypatch):
    cfg = {}
    _patch_cfg(monkeypatch, cfg)
    assert pending.pending() is None


def test_stale_pending_read_as_none(monkeypatch):
    cfg = {"app.pending_action": "limit", "app.pending_ts": _iso(-10), "app.edit_card_id": "2"}
    upserts = _patch_cfg(monkeypatch, cfg)
    assert pending.pending() is None
    assert upserts == []  # read-only; the router clears stale explicitly


def test_read_pending_reports_stale_without_clearing(monkeypatch):
    cfg = {"app.pending_action": "cutoff", "app.pending_ts": _iso(-10), "app.edit_card_id": "2"}
    upserts = _patch_cfg(monkeypatch, cfg)
    assert pending.read_pending() == ("stale", "cutoff", 2, "list")
    assert upserts == []  # untouched — router decides what to do


def test_read_pending_fresh_and_none(monkeypatch):
    cfg = {}
    _patch_cfg(monkeypatch, cfg)
    assert pending.read_pending() is None
    cfg.update({"app.pending_action": "limit", "app.pending_ts": _iso(), "app.edit_card_id": "2"})
    assert pending.read_pending() == ("fresh", "limit", 2, "list")


def test_clear_is_noop_when_empty(monkeypatch):
    cfg = {}
    upserts = _patch_cfg(monkeypatch, cfg)
    pending.clear_pending()
    assert upserts == []


# --- routing: consume pending free text ---

def _patch_flow(monkeypatch, cfg):
    _patch_cfg(monkeypatch, cfg)
    monkeypatch.setattr("core.sheets.get_cards", lambda: [BNI, TOKOPEDIA])
    monkeypatch.setattr("core.sheets.get_default_card", lambda: BNI)
    return cfg


def test_route_consumes_limit_value_and_clears(monkeypatch):
    cfg = _patch_flow(monkeypatch, {"app.pending_action": "limit", "app.pending_ts": _iso(), "app.edit_card_id": "2"})
    calls = []
    monkeypatch.setattr("core.sheets.update_card_limit", lambda cid, amt: calls.append((cid, amt)))
    reply, _ = w._route({"text": "9000000"})
    assert calls == [(2, 9000000)]
    assert "Tokopedia Card" in reply
    assert cfg.get("app.pending_action") == ""  # cleared on success


def test_route_keeps_pending_on_error(monkeypatch):
    cfg = _patch_flow(monkeypatch, {"app.pending_action": "cutoff", "app.pending_ts": _iso(), "app.edit_card_id": "2"})
    reply, _ = w._route({"text": "40"})
    assert "cutoff must be 1–28" in reply
    assert cfg.get("app.pending_action") == "cutoff"  # D1: stays for retype


def test_menu_button_tap_clears_pending(monkeypatch):
    cfg = _patch_flow(monkeypatch, {"app.pending_action": "limit", "app.pending_ts": _iso(), "app.edit_card_id": "2"})
    monkeypatch.setattr("api.webhook.summary.handle", lambda: "SUMMARY-OK")
    reply, _ = w._route({"text": menu.BTN_SUMMARY})
    assert reply == "SUMMARY-OK"
    assert cfg.get("app.pending_action") == ""


def test_slash_clears_pending(monkeypatch):
    cfg = _patch_flow(monkeypatch, {"app.pending_action": "limit", "app.pending_ts": _iso(), "app.edit_card_id": "2"})
    reply, _ = w._route({"text": "/start"})
    assert "CardCycle" in reply  # menu shown
    assert cfg.get("app.pending_action") == ""


def test_route_does_not_capture_plain_text_without_pending(monkeypatch):
    _patch_flow(monkeypatch, {})
    reply, _ = w._route({"text": "asdfghjkl"})
    assert reply == w.FALLBACK


def test_route_stale_pending_numeric_guided_not_expense(monkeypatch):
    # cutoff expired 5+ min ago; typing a bare number must not become an expense
    cfg = {"app.pending_action": "cutoff", "app.pending_ts": _iso(-10), "app.edit_card_id": "2"}
    _patch_flow(monkeypatch, cfg)
    monkeypatch.setattr("core.sheets.append_transactions", lambda rows: (_ for _ in ()).throw(AssertionError("must not append")))
    reply, _ = w._route({"text": "222"})
    assert "expired" in reply and "Recorded" not in reply
    assert cfg.get("app.pending_action") == ""  # cleared after guidance


def test_route_stale_pending_text_falls_through(monkeypatch):
    # stale + non-numeric text is not an old answer → normal routing
    cfg = {"app.pending_action": "cutoff", "app.pending_ts": _iso(-10), "app.edit_card_id": "2"}
    _patch_flow(monkeypatch, cfg)
    reply, _ = w._route({"text": "asdfghjkl"})
    assert reply == w.FALLBACK
    assert cfg.get("app.pending_action") == ""


def test_cancel_callback_clears_pending(monkeypatch):
    cfg = _patch_flow(monkeypatch, {"app.pending_action": "limit", "app.pending_ts": _iso(), "app.edit_card_id": "2"})
    edited = []
    monkeypatch.setattr("api.webhook.edit_telegram", lambda chat, mid, text, reply_markup=None: edited.append(text))
    w._handle_callback({"id": "1", "data": "cards:cancel", "message": {"chat": {"id": 1}, "message_id": 5}})
    assert cfg.get("app.pending_action") == ""
    assert edited and "Cancelled" in edited[0]


def test_cutoff_callback_sets_normalized_pending_action(monkeypatch):
    # regression: callback tokens are the canonical names (no cut/cutoff split)
    cfg = {}
    _patch_flow(monkeypatch, cfg)
    monkeypatch.setattr("core.sheets.get_card", lambda cid: TOKOPEDIA if cid == 2 else None)
    monkeypatch.setattr("core.sheets.get_cards", lambda: [BNI, TOKOPEDIA])
    monkeypatch.setattr("api.webhook.send_telegram", lambda chat, text, reply_markup=None: None)
    w._handle_callback({"id": "1", "data": "cards:cutoff:2", "message": {"chat": {"id": 1}, "message_id": 5}})
    assert '"a": "cutoff"' in cfg.get("app.pending", "")


# --- replied legacy prompt without pending → generic error (never expense) ---

def test_reply_to_stale_cards_prompt_not_recorded_as_expense(monkeypatch):
    _patch_flow(monkeypatch, {})
    msg = {"text": "222", "reply_to_message": {"text": prompts.PROMPT_CARDS_CUTOFF}}
    reply, _ = w._route(msg)
    assert reply == w.FALLBACK
    assert "Recorded" not in reply


def test_reply_to_active_cards_prompt_applies_value(monkeypatch):
    cfg = _patch_flow(monkeypatch, {"app.pending_action": "cutoff", "app.pending_ts": _iso(), "app.edit_card_id": "2"})
    calls = []
    monkeypatch.setattr("core.sheets.update_card_cutoff", lambda cid, day: calls.append((cid, day)))
    msg = {"text": "27", "reply_to_message": {"text": prompts.PROMPT_CARDS_CUTOFF}}
    reply, _ = w._route(msg)
    assert calls == [(2, 27)]
    assert cfg.get("app.pending_action") == ""
