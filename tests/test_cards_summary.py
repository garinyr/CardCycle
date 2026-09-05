"""tests/test_cards_summary.py — MVP2 P3: 🗂 Cards management + 📊 Summary."""

from datetime import date

import api.commands.cards as cards
import api.commands.summary as summary

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


# --- add ---

def test_cards_add_valid(monkeypatch):
    _patch(monkeypatch, cards_list=[], default=None)
    added = []
    monkeypatch.setattr("core.sheets.allocate_card_id", lambda: 7)
    monkeypatch.setattr("core.sheets.add_card", lambda *a: added.append(a))
    out = cards.add_reply("Tokopedia Card 8000000 cutoff 27")
    assert "Card added: Tokopedia Card" in out
    assert added == [(7, "Tokopedia Card", 8000000, 27)]


def test_cards_add_default_cutoff(monkeypatch):
    _patch(monkeypatch, cards_list=[], default=None)
    added = []
    monkeypatch.setattr("core.sheets.allocate_card_id", lambda: 8)
    monkeypatch.setattr("core.sheets.add_card", lambda *a: added.append(a))
    cards.add_reply("BCA Everyday 5000000")
    assert added == [(8, "BCA Everyday", 5000000, 13)]


def test_cards_add_invalid_cutoff(monkeypatch):
    _patch(monkeypatch, cards_list=[], default=None)
    out = cards.add_reply("X 1000 cutoff 40")
    assert "cutoff must be 1–28" in out


def test_cards_add_duplicate_name_rejected(monkeypatch):
    _patch(monkeypatch, default=BNI)
    out = cards.add_reply("BNI Mastercard 2000000")
    assert "already exists" in out


# --- default / limit / cutoff actions ---

def test_cards_default_reply(monkeypatch):
    _patch(monkeypatch, default=BNI)
    calls = []
    monkeypatch.setattr("core.sheets.set_config", lambda k, v: calls.append((k, v)))
    out = cards.default_reply("@tokopedia")
    assert calls == [("default_card_id", "2")]
    assert "Default card: Tokopedia Card" in out


def test_cards_limit_reply(monkeypatch):
    _patch(monkeypatch, default=BNI)
    calls = []
    monkeypatch.setattr("core.sheets.update_card_limit", lambda cid, amt: calls.append((cid, amt)))
    out = cards.limit_reply("@tokopedia 9000000")
    assert calls == [(2, 9000000)]
    assert "Tokopedia Card" in out


def test_cards_limit_reply_default_when_no_at(monkeypatch):
    _patch(monkeypatch, default=BNI)
    calls = []
    monkeypatch.setattr("core.sheets.update_card_limit", lambda cid, amt: calls.append((cid, amt)))
    cards.limit_reply("12000000")
    assert calls == [(1, 12000000)]


def test_cards_cutoff_reply(monkeypatch):
    _patch(monkeypatch, default=BNI)
    calls = []
    monkeypatch.setattr("core.sheets.update_card_cutoff", lambda cid, day: calls.append((cid, day)))
    out = cards.cutoff_reply("@tokopedia 5")
    assert calls == [(2, 5)]
    assert "Tokopedia Card" in out


def test_cards_cutoff_reply_invalid_day(monkeypatch):
    _patch(monkeypatch, default=BNI)
    out = cards.cutoff_reply("@tokopedia 40")
    assert "cutoff must be 1–28" in out


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
