"""tests/test_route_menu_buttons.py — routing-level checks for the Cards/Summary
menu buttons.

Layer rule (testing pyramid): this file only asserts the *routing glue* —
button label → the right flow entry + markup shape. Handler output text is
owned by the handler suites (test_cards_summary, test_summary_*), so handlers
are stubbed here to markers; the same assertion set is never duplicated.
"""

import api.webhook as w
from core import menu

BNI = {"card_id": 1, "card_name": "BNI Mastercard", "bank": "BNI", "card_limit": 15000000, "cutoff_day": 13, "is_active": True}
TOKOPEDIA = {"card_id": 2, "card_name": "Tokopedia Card", "bank": "Tokopedia", "card_limit": 8000000, "cutoff_day": 27, "is_active": True}


def _patch_sheets(monkeypatch):
    monkeypatch.setattr("core.sheets.get_cards", lambda: [BNI, TOKOPEDIA])
    monkeypatch.setattr("core.sheets.get_default_card", lambda: BNI)
    monkeypatch.setattr("core.sheets.get_config", lambda: {})


def test_route_cards_label_dispatches_to_cards_flow(monkeypatch):
    _patch_sheets(monkeypatch)
    monkeypatch.setattr("api.webhook.cards.view", lambda: "CARDS-VIEW")
    reply, markup = w._route({"text": menu.BTN_CARDS})
    assert reply == "CARDS-VIEW"
    # per-row action callbacks (tap picks the card) + Add row
    flat = [b["callback_data"] for row in markup.get("inline_keyboard", []) for b in row]
    assert "cards:lmt:2" in flat and "cards:main:2" in flat and "cards:add" in flat


def test_route_summary_label_dispatches_to_summary(monkeypatch):
    _patch_sheets(monkeypatch)
    monkeypatch.setattr("api.webhook.summary.handle", lambda: "SUMMARY-OK")
    reply, markup = w._route({"text": menu.BTN_SUMMARY})
    assert reply == "SUMMARY-OK"
    assert "keyboard" in markup  # menu re-attached
