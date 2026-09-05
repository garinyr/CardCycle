"""tests/test_route_menu_buttons.py — routing-level checks for the Cards/Summary
menu buttons.

Layer rule (testing pyramid): this file only asserts the *routing glue* —
button label → the right flow entry + markup shape. Handler output text is
owned by the handler suites (test_cards_summary), so handlers are stubbed here
to markers; the same assertion set is never duplicated.
"""

import api.webhook as w
from core import menu

BNI = {"card_id": 1, "card_name": "BNI Mastercard", "bank": "BNI", "card_limit": 15000000, "cutoff_day": 13, "is_active": True}
TOKOPEDIA = {"card_id": 2, "card_name": "Tokopedia Card", "bank": "Tokopedia", "card_limit": 8000000, "cutoff_day": 27, "is_active": True}


def _patch_sheets(monkeypatch):
    monkeypatch.setattr("core.sheets.get_cards", lambda: [BNI, TOKOPEDIA])
    monkeypatch.setattr("core.sheets.get_default_card", lambda: BNI)
    monkeypatch.setattr("core.sheets.get_config", lambda: {})


def _flat(markup):
    return [b["callback_data"] for row in markup.get("inline_keyboard", []) for b in row]


def test_route_cards_label_dispatches_to_cards_flow(monkeypatch):
    _patch_sheets(monkeypatch)
    monkeypatch.setattr("api.webhook.cards.view", lambda: "CARDS-VIEW")
    reply, markup = w._route({"text": menu.BTN_CARDS})
    assert reply == "CARDS-VIEW"
    # picker: one tappable row per active card + Add (no duplicated actions)
    flat = _flat(markup)
    assert "cards:sel:1" in flat and "cards:sel:2" in flat and "cards:add" in flat
    assert not any(cb.startswith("cards:lmt:") or cb.startswith("cards:cut:") for cb in flat)


def test_select_card_opens_single_action_menu(monkeypatch):
    _patch_sheets(monkeypatch)
    monkeypatch.setattr("core.sheets.get_card", lambda cid: {1: BNI, 2: TOKOPEDIA}.get(cid))
    calls = []
    monkeypatch.setattr("api.webhook.edit_telegram", lambda chat, mid, text, reply_markup=None: calls.append((text, reply_markup)))
    w._handle_callback({"id": "1", "data": "cards:sel:2", "message": {"chat": {"id": 1}, "message_id": 9}})
    assert calls
    text, markup = calls[0]
    assert "Tokopedia Card" in text
    flat = _flat(markup)
    # exactly one action row for this card (+ Back) — no cross-card duplication
    assert "cards:lmt:2" in flat and "cards:cut:2" in flat and "cards:main:2" in flat
    assert "cards:lmt:1" not in flat and "cards:list" in flat


def test_route_summary_label_dispatches_to_summary(monkeypatch):
    _patch_sheets(monkeypatch)
    monkeypatch.setattr("api.webhook.summary.handle", lambda: "SUMMARY-OK")
    reply, markup = w._route({"text": menu.BTN_SUMMARY})
    assert reply == "SUMMARY-OK"
    assert "keyboard" in markup  # menu re-attached


# --- answered-prompt cleanup (cards prompts are deleted after use) ---

from core import prompts


def test_answered_cards_prompt_is_deleted(monkeypatch):
    deleted = []
    monkeypatch.setattr("api.webhook.delete_message", lambda chat, mid: deleted.append((chat, mid)))
    msg = {"text": "8000000", "reply_to_message": {"message_id": 55, "text": prompts.PROMPT_CARDS_LIMIT}}
    w._cleanup_answered_prompt(msg, 123)
    assert deleted == [(123, 55)]


def test_answered_non_cleanup_prompt_not_deleted(monkeypatch):
    deleted = []
    monkeypatch.setattr("api.webhook.delete_message", lambda chat, mid: deleted.append((chat, mid)))
    msg = {"text": "150000 Lunch", "reply_to_message": {"message_id": 56, "text": prompts.PROMPT_EXPENSE_INPUT}}
    w._cleanup_answered_prompt(msg, 123)
    assert deleted == []
