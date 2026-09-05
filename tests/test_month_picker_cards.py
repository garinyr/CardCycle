"""tests/test_month_picker_cards.py — MVP2 P4: card-scoped month picker + All cards.

Statement/running inline tokens now carry the card id; the `🗂 All cards`
nav (single mechanism, any count > 1) opens a picker and re-renders per card.
"""

from datetime import date

import api.webhook as w
from core import menu

BNI = {"card_id": 1, "card_name": "BNI Mastercard", "bank": "BNI", "card_limit": 15000000, "cutoff_day": 13, "is_active": True}
TOKOPEDIA = {"card_id": 2, "card_name": "Tokopedia Card", "bank": "Tokopedia", "card_limit": 8000000, "cutoff_day": 27, "is_active": True}


def _patch(monkeypatch, cards=None, default=BNI, txns=None):
    monkeypatch.setattr("core.sheets.get_cards", lambda: cards if cards is not None else [BNI, TOKOPEDIA])
    monkeypatch.setattr("core.sheets.get_default_card", lambda: default)
    monkeypatch.setattr("core.sheets.read_transactions", lambda: txns if txns is not None else [])
    monkeypatch.setattr("core.sheets.get_card", lambda cid: {1: BNI, 2: TOKOPEDIA}.get(cid))


def _capture_edit(monkeypatch):
    calls = []
    monkeypatch.setattr("api.webhook.edit_telegram", lambda chat, mid, text, reply_markup=None: calls.append((chat, mid, text, reply_markup)))
    return calls


def test_month_keyboard_tokens_carry_card_id(monkeypatch):
    kb = menu.month_keyboard(date(2026, 9, 5), 13, prefix="stmt", card_id=2, count=3)
    buttons = [b for row in kb["inline_keyboard"] for b in row]
    assert any(b["callback_data"].startswith("stmt:2:") for b in buttons)


def test_detail_toggle_token_carries_card_id():
    kb = menu.month_keyboard(date(2026, 9, 5), 13, prefix="run", card_id=2, months=False)
    detail = kb["inline_keyboard"][0][0]
    assert detail["callback_data"].startswith("run:2:")


def test_other_month_hidden_for_non_default_card():
    # stateless rule: typed Other-month targets the default card, so the button
    # only exists on the default card's view.
    kb = menu.month_keyboard(date(2026, 9, 5), 13, prefix="stmt", card_id=1, show_other=True)
    flat = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
    assert any(cb.startswith("stmt:other:1") for cb in flat)
    kb2 = menu.month_keyboard(date(2026, 9, 5), 13, prefix="stmt", card_id=2, show_other=False)
    flat2 = [b["callback_data"] for row in kb2["inline_keyboard"] for b in row]
    assert not any(cb.startswith("stmt:other") for cb in flat2)


def test_view_markup_adds_all_cards_nav_when_multiple(monkeypatch):
    _patch(monkeypatch)
    markup = w._view_markup(BNI, "stmt")
    flat = [b["callback_data"] for row in markup["inline_keyboard"] for b in row]
    assert "stmt:all:1" in flat


def test_view_markup_no_all_cards_when_single(monkeypatch):
    _patch(monkeypatch, cards=[BNI])
    markup = w._view_markup(BNI, "stmt")
    flat = [b["callback_data"] for row in markup["inline_keyboard"] for b in row]
    assert not any(cb.startswith("stmt:all") for cb in flat)


def test_all_cards_callback_opens_picker(monkeypatch):
    _patch(monkeypatch)
    calls = _capture_edit(monkeypatch)
    w._month_callback(["stmt", "all", "1"], 1, 10)
    assert calls
    _, _, text, markup = calls[0]
    assert "pick a card" in text.lower()
    flat = [b["callback_data"] for row in markup["inline_keyboard"] for b in row]
    assert "stmt:view:2" in flat and "stmt:back:1" in flat


def test_pick_callback_renders_card(monkeypatch):
    _patch(monkeypatch)
    calls = _capture_edit(monkeypatch)
    w._month_callback(["stmt", "view", "2"], 1, 10)
    assert calls
    _, _, text, _ = calls[0]
    # latest frozen for Tokopedia (cutoff 27) — anchored off the running cycle
    assert "Tokopedia Card" in text and "August 2026" in text


def test_month_tap_renders_card(monkeypatch):
    _patch(monkeypatch)
    calls = _capture_edit(monkeypatch)
    w._month_callback(["stmt", "2", "sep26"], 1, 10)
    assert calls
    _, _, text, markup = calls[0]
    assert "Tokopedia Card" in text and "September 2026" in text
    flat = [b["callback_data"] for row in markup["inline_keyboard"] for b in row]
    assert any(cb.startswith("stmt:2:") for cb in flat)
