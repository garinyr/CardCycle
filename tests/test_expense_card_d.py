"""tests/test_expense_card_d.py — MVP2 Expense Option D (sticky card + chips).

Covers the sticky `Config.expense_card_id` behavior in api.commands.expense and
the chip-picker callbacks in api.webhook.
"""

import api.commands.expense as expense
import api.webhook as w
from core import prompts

BNI = {"card_id": 1, "card_name": "BNI Mastercard", "card_limit": 15000000, "cutoff_day": 13, "is_active": True}
TOKOPEDIA = {"card_id": 2, "card_name": "Tokopedia Card", "card_limit": 8000000, "cutoff_day": 27, "is_active": True}


def _patch_sheets(monkeypatch, config=None, default=BNI, cards=None):
    appended = []
    monkeypatch.setattr("core.sheets.get_default_card", lambda: default)
    monkeypatch.setattr("core.sheets.get_config", lambda: config if config is not None else {})
    monkeypatch.setattr("core.sheets.get_cards", lambda: cards if cards is not None else [BNI, TOKOPEDIA])
    monkeypatch.setattr("core.sheets.allocate_ids", lambda count=1: 100)
    monkeypatch.setattr("core.sheets.append_transactions", lambda rows: appended.extend(rows))
    return appended


# --- expense.handle target resolution ---

def test_no_sticky_no_at_uses_default(monkeypatch):
    appended = _patch_sheets(monkeypatch)
    out = expense.handle("150000 Lunch")
    assert appended and appended[0]["card_id"] == 1
    assert "1 saved" in out


def test_sticky_card_used_for_expense(monkeypatch):
    appended = _patch_sheets(monkeypatch, config={"expense_card_id": "2"})
    out = expense.handle("150000 Lunch")
    assert appended and appended[0]["card_id"] == 2
    assert "Tokopedia Card" in out  # confirmation line names the card


def test_sticky_invalid_falls_back_to_default(monkeypatch):
    appended = _patch_sheets(monkeypatch, config={"expense_card_id": "99"})
    out = expense.handle("150000 Lunch")
    assert appended and appended[0]["card_id"] == 1
    assert "Tokopedia Card" not in out


def test_sticky_deactivated_card_falls_back(monkeypatch):
    inactive = dict(TOKOPEDIA, is_active=False)
    appended = _patch_sheets(monkeypatch, config={"expense_card_id": "2"}, cards=[BNI, inactive])
    out = expense.handle("150000 Lunch")
    assert appended and appended[0]["card_id"] == 1


def test_at_override_beats_sticky(monkeypatch):
    appended = _patch_sheets(monkeypatch, config={"expense_card_id": "2"})
    out = expense.handle("@bni 150000 Lunch")
    assert appended and appended[0]["card_id"] == 1


def test_unknown_at_raises_clear_error(monkeypatch):
    appended = _patch_sheets(monkeypatch, config={"expense_card_id": "2"})
    out = expense.handle("@nope 150000 Lunch")
    assert "Unknown card: @nope" in out
    assert appended == []


# --- webhook chip-picker flow ---

def test_expense_entry_single_active_card_straight_to_prompt(monkeypatch):
    _patch_sheets(monkeypatch, cards=[BNI])
    text, markup = w._expense_entry()
    assert text == prompts.PROMPT_EXPENSE_INPUT
    assert markup.get("force_reply") is True


def test_expense_entry_multi_card_shows_chips(monkeypatch):
    _patch_sheets(monkeypatch)
    text, markup = w._expense_entry()
    assert "record to which card" in text.lower()
    inline = markup["inline_keyboard"][0]
    assert "exp:pick:1" in inline[0]["callback_data"]  # current (default) chip
    assert inline[-1]["callback_data"] == "exp:other"


def test_expense_pick_sets_sticky_and_sends_prompt(monkeypatch):
    _patch_sheets(monkeypatch)
    sent = []
    upserts = []
    monkeypatch.setattr("api.webhook.send_telegram", lambda chat, text, reply_markup=None: sent.append((text, reply_markup)))
    monkeypatch.setattr("core.sheets.upsert_config", lambda k, v: upserts.append((k, v)))
    monkeypatch.setattr("core.sheets.get_card", lambda cid: TOKOPEDIA)
    w._expense_callback("pick", 123, 456, "2")
    assert upserts == [("expense_card_id", "2")]
    assert len(sent) == 1
    text, markup = sent[0]
    assert text == prompts.PROMPT_EXPENSE_INPUT
    assert "Recording to Tokopedia Card" in markup["input_field_placeholder"]
    assert markup.get("force_reply") is True


def test_expense_pick_inactive_card_ignored(monkeypatch):
    _patch_sheets(monkeypatch)
    inactive = dict(TOKOPEDIA, is_active=False)
    monkeypatch.setattr("core.sheets.get_card", lambda cid: inactive)
    sent = []
    monkeypatch.setattr("api.webhook.send_telegram", lambda chat, text, reply_markup=None: sent.append(1))
    w._expense_callback("pick", 123, 456, "2")
    assert sent == []


def test_chip_callback_real_update_sends_prompt(monkeypatch):
    # regression: tapping an expense chip (exp:pick:1) must reach _send_expense_prompt
    _patch_sheets(monkeypatch)
    monkeypatch.setattr("api.webhook.answer_callback", lambda cid: None)
    monkeypatch.setattr("api.webhook.edit_telegram", lambda *a, **k: None)
    monkeypatch.setattr("core.sheets.upsert_config", lambda k, v: None)
    monkeypatch.setattr("core.sheets.get_card", lambda cid: BNI if cid == 1 else None)
    sent = []
    monkeypatch.setattr("api.webhook.send_telegram", lambda chat, text, reply_markup=None: sent.append((text, reply_markup)))
    w._handle_callback({"id": "1", "data": "exp:pick:1", "message": {"chat": {"id": 1}, "message_id": 9}})
    assert sent and sent[0][0] == prompts.PROMPT_EXPENSE_INPUT
