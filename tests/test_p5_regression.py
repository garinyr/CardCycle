"""tests/test_p5_regression.py — MVP2 P5: routing-level regression for new labels.

End-to-end `_route` for the 🗂 Cards / 📊 Summary buttons (patched sheets) plus
a reminder that MVP1 routing contracts (slash redirect, fallback, prompt
match) still hold — those live in test_webhook_routing.py.
"""

import api.webhook as w
from core import menu

BNI = {"card_id": 1, "card_name": "BNI Mastercard", "bank": "BNI", "card_limit": 15000000, "cutoff_day": 13, "is_active": True}
TOKOPEDIA = {"card_id": 2, "card_name": "Tokopedia Card", "bank": "Tokopedia", "card_limit": 8000000, "cutoff_day": 27, "is_active": True}


def _patch(monkeypatch, txns=None):
    monkeypatch.setattr("core.sheets.get_cards", lambda: [BNI, TOKOPEDIA])
    monkeypatch.setattr("core.sheets.get_default_card", lambda: BNI)
    monkeypatch.setattr("core.sheets.get_config", lambda: {})
    monkeypatch.setattr("core.sheets.read_transactions", lambda: txns if txns is not None else [])


def test_route_cards_label_returns_view_with_actions(monkeypatch):
    _patch(monkeypatch)
    reply, markup = w._route({"text": menu.BTN_CARDS})
    assert "1. BNI Mastercard" in reply and "⭐ default" in reply
    # inline action row present (callback prefix cards:)
    flat = [b["callback_data"] for row in markup.get("inline_keyboard", []) for b in row]
    assert "cards:add" in flat and "cards:cutoff" in flat


def test_route_summary_label_returns_summary(monkeypatch):
    _patch(monkeypatch, txns=[])
    reply, markup = w._route({"text": menu.BTN_SUMMARY})
    assert "Summary" in reply and "BNI Mastercard" in reply
    assert "keyboard" in markup  # menu re-attached


def test_single_active_card_keeps_mvp1_expense_flow(monkeypatch):
    # 1 active card → expense button goes straight to the prompt (v1.0.0 path).
    monkeypatch.setattr("core.sheets.get_cards", lambda: [BNI])
    monkeypatch.setattr("core.sheets.get_default_card", lambda: BNI)
    monkeypatch.setattr("core.sheets.get_config", lambda: {})
    reply, markup = w._route({"text": menu.BTN_EXPENSE})
    assert "Type amount + description" in reply
    assert markup.get("force_reply") is True
