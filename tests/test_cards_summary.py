"""tests/test_cards_summary.py — MVP2 P3: 🗂 Cards management + 📊 Summary."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import api.commands.cards as cards
import api.commands.summary as summary

TZ = ZoneInfo("Asia/Jakarta")


def _now_iso():
    return datetime.now(TZ).isoformat(timespec="seconds")


def _pending_cfg(action, card_id):
    return {
        "app.pending_action": action,
        "app.pending_ts": _now_iso(),
        "app.edit_card_id": str(card_id),
    }

BNI = {"card_id": 1, "card_name": "BNI Mastercard", "bank": "BNI", "card_limit": 15000000, "cutoff_day": 13, "is_active": True}
TOKOPEDIA = {"card_id": 2, "card_name": "Tokopedia Card", "bank": "Tokopedia", "card_limit": 8000000, "cutoff_day": 27, "is_active": True}


def _patch(monkeypatch, cards_list=None, default=None, txns=None, config=None):
    monkeypatch.setattr("core.sheets.get_cards", lambda: cards_list if cards_list is not None else [BNI, TOKOPEDIA])
    monkeypatch.setattr("core.sheets.get_default_card", lambda: default)
    monkeypatch.setattr("core.sheets.get_config", lambda: config or {})
    monkeypatch.setattr("core.sheets.read_transactions", lambda: txns if txns is not None else [])


# --- cards view ---

def test_cards_view_lists_cards_with_flags(monkeypatch):
    _patch(monkeypatch, default=BNI)
    out = cards.view()
    assert "1. BNI Mastercard" in out and "⭐ default" in out
    assert "2. Tokopedia Card" in out


def test_cards_view_inactive_flag(monkeypatch):
    inactive = dict(TOKOPEDIA, is_active=False)
    _patch(monkeypatch, cards_list=[BNI, inactive], default=BNI)
    out = cards.view()
    assert "inactive" in out


def test_cards_view_empty(monkeypatch):
    _patch(monkeypatch, cards_list=[], default=None)
    out = cards.view()
    assert "No cards yet" in out


# --- add (typed → confirm before write) ---

def _patch_flow(monkeypatch, default=None, cards_list=None):
    cfg = {}
    _patch(monkeypatch, cards_list=cards_list, default=default, config=cfg)
    upserts = []

    def _upsert(k, v):
        cfg[k] = v
        upserts.append((k, v))

    monkeypatch.setattr("core.sheets.upsert_config", _upsert)
    return cfg, upserts


def test_cards_add_preview_then_confirm_writes(monkeypatch):
    _patch_flow(monkeypatch, cards_list=[], default=None)
    added = []
    monkeypatch.setattr("core.sheets.allocate_card_id", lambda: 7)
    monkeypatch.setattr("core.sheets.add_card", lambda *a: added.append(a))
    text, markup = cards.start_add("Tokopedia Card 8000000 cutoff 27")
    assert "Add this card?" in text and "Tokopedia Card" in text
    assert markup is None
    out = cards.confirm_add(True)
    assert "Card added: Tokopedia Card" in out
    assert added == [(7, "Tokopedia Card", 8000000, 27)]


def test_cards_add_default_cutoff_on_confirm(monkeypatch):
    _patch_flow(monkeypatch, cards_list=[], default=None)
    added = []
    monkeypatch.setattr("core.sheets.allocate_card_id", lambda: 8)
    monkeypatch.setattr("core.sheets.add_card", lambda *a: added.append(a))
    cards.start_add("BCA Everyday 5000000")
    cards.confirm_add(True)
    assert added == [(8, "BCA Everyday", 5000000, 13)]


def test_cards_add_denied_writes_nothing(monkeypatch):
    _patch_flow(monkeypatch, cards_list=[], default=None)
    added = []
    monkeypatch.setattr("core.sheets.allocate_card_id", lambda: 7)
    monkeypatch.setattr("core.sheets.add_card", lambda *a: added.append(a))
    cards.start_add("BCA Everyday 5000000")
    out = cards.confirm_add(False)
    assert "cancelled" in out.lower()
    assert added == []


def test_cards_add_invalid_cutoff(monkeypatch):
    _patch_flow(monkeypatch, cards_list=[], default=None)
    text, _ = cards.start_add("X 1000 cutoff 40")
    assert "cutoff must be 1–28" in text


def test_cards_add_duplicate_name_rejected(monkeypatch):
    _patch_flow(monkeypatch, default=BNI)
    text, _ = cards.start_add("BNI Mastercard 2000000")
    assert "already exists" in text


# --- default (tap) / limit / cutoff (value-only via pending target) ---

def _patch_actions(monkeypatch, config=None):
    _patch(monkeypatch, default=BNI, config=config or {})
    upserts = []
    monkeypatch.setattr("core.sheets.upsert_config", lambda k, v: upserts.append((k, v)))
    return upserts


def test_cards_set_main(monkeypatch):
    _patch(monkeypatch, default=BNI)
    calls = []
    monkeypatch.setattr("core.sheets.set_config", lambda k, v: calls.append((k, v)))
    out = cards.set_main(2)
    assert calls == [("default_card_id", "2")]
    assert "Default card: Tokopedia Card" in out


def test_cards_limit_value_only_uses_pending_card(monkeypatch):
    _patch_actions(monkeypatch, config=_pending_cfg("limit", 2))
    calls = []
    monkeypatch.setattr("core.sheets.update_card_limit", lambda cid, amt: calls.append((cid, amt)))
    out = cards.limit_reply("9000000")
    assert calls == [(2, 9000000)]
    assert "Tokopedia Card" in out


def test_cards_limit_without_pending_uses_default(monkeypatch):
    _patch_actions(monkeypatch)
    calls = []
    monkeypatch.setattr("core.sheets.update_card_limit", lambda cid, amt: calls.append((cid, amt)))
    out = cards.limit_reply("12000000")
    assert calls == [(1, 12000000)]
    assert "BNI Mastercard" in out


def test_cards_limit_at_still_overrides_pending(monkeypatch):
    _patch_actions(monkeypatch, config=_pending_cfg("limit", 2))
    calls = []
    monkeypatch.setattr("core.sheets.update_card_limit", lambda cid, amt: calls.append((cid, amt)))
    out = cards.limit_reply("@bni 15000000")
    assert calls == [(1, 15000000)]
    assert "BNI Mastercard" in out


def test_cards_cutoff_value_only_uses_pending_card(monkeypatch):
    _patch_actions(monkeypatch, config=_pending_cfg("cutoff", 2))
    calls = []
    monkeypatch.setattr("core.sheets.update_card_cutoff", lambda cid, day: calls.append((cid, day)))
    out = cards.cutoff_reply("5")
    assert calls == [(2, 5)]
    assert "Tokopedia Card" in out


def test_cards_cutoff_invalid_day_keeps_pending(monkeypatch):
    # D1: validation error → pending stays for an immediate retype.
    _patch_actions(monkeypatch, config=_pending_cfg("cutoff", 2))
    out = cards.cutoff_reply("40")
    assert "cutoff must be 1–28" in out
    assert _pending_cfg("cutoff", 2)["app.pending_action"]  # (state not consumed here; router clears on success)


# --- summary ---

def test_summary_per_card_running_totals(monkeypatch):
    monkeypatch.setattr("api.commands.summary.today_wib", lambda: date(2026, 9, 5))
    txns = [
        {"id": 1, "card_id": 1, "date": "2026-09-01", "amount": 150000, "description": "lunch", "deleted": False},
        {"id": 2, "card_id": 2, "date": "2026-09-20", "amount": 200000, "description": "game", "deleted": False},
        {"id": 3, "card_id": 2, "date": "2026-09-21", "amount": 999999, "description": "deleted row", "deleted": True},
    ]
    _patch(monkeypatch, default=BNI, txns=txns)
    out = summary.handle()
    assert "BNI Mastercard ⭐" in out and "Rp 150.000" in out
    assert "Tokopedia Card" in out and "Rp 200.000" in out
    assert "Rp 999.999" not in out  # soft-deleted excluded


def test_summary_no_active_cards(monkeypatch):
    inactive = dict(BNI, is_active=False)
    _patch(monkeypatch, cards_list=[inactive], default=None)
    out = summary.handle()
    assert "No active cards yet" in out
