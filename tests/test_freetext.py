"""tests/test_freetext.py — free-text routing plan: bare-number confirm (D2),
bare-month hint (D3), targeted fallback hints."""

import api.webhook as w
from core import freetext, menu

BNI = {"card_id": 1, "card_name": "BNI Mastercard", "bank": "BNI", "card_limit": 15000000, "cutoff_day": 13, "is_active": True}


def _patch_empty(monkeypatch):
    monkeypatch.setattr("core.sheets.get_config", lambda: {})
    monkeypatch.setattr("core.sheets.get_default_card", lambda: BNI)
    monkeypatch.setattr("core.sheets.get_cards", lambda: [BNI])
    monkeypatch.setattr("core.sheets.upsert_config", lambda k, v: None)


def _flat(markup):
    return [b["callback_data"] for row in markup.get("inline_keyboard", []) for b in row]


# --- D2: bare number → confirm, never silent ---

def test_bare_number_asks_confirmation(monkeypatch):
    _patch_empty(monkeypatch)
    reply, markup = w._route({"text": "222"})
    assert "as an expense" in reply
    assert "exp:record_yes" in _flat(markup) and "exp:record_no" in _flat(markup)


def test_confirm_yes_records_expense(monkeypatch):
    cfg = {}
    monkeypatch.setattr("core.sheets.get_config", lambda: cfg)
    monkeypatch.setattr("core.sheets.upsert_config", lambda k, v: cfg.__setitem__(k, v))
    calls = []
    monkeypatch.setattr("api.webhook.expense.handle", lambda t: f"expense-handled:{t}")
    edited = []
    monkeypatch.setattr("api.webhook.edit_telegram", lambda chat, mid, text, reply_markup=None: edited.append((text, reply_markup)))
    from core import pending as p
    p.save_draft("*", 222, 0)
    w._handle_callback({"id": "1", "data": "exp:record_yes", "message": {"chat": {"id": 1}, "message_id": 9}})
    assert edited and edited[0][0] == "expense-handled:222"


def test_confirm_no_cancels(monkeypatch):
    cfg = {}
    monkeypatch.setattr("core.sheets.get_config", lambda: cfg)
    monkeypatch.setattr("core.sheets.upsert_config", lambda k, v: cfg.__setitem__(k, v))
    from core import pending as p
    p.save_draft("*", 222, 0)
    edited = []
    monkeypatch.setattr("api.webhook.edit_telegram", lambda chat, mid, text, reply_markup=None: edited.append(text))
    w._handle_callback({"id": "1", "data": "exp:record_no", "message": {"chat": {"id": 1}, "message_id": 9}})
    assert edited and "cancelled" in edited[0].lower()


# --- D3: bare month → hint ---

def test_bare_month_gets_statement_hint(monkeypatch):
    _patch_empty(monkeypatch)
    reply, _ = w._route({"text": "sep26"})
    assert "Statement" in reply and "Running" in reply
    assert "Recorded" not in reply


def test_card_ref_gets_cards_hint(monkeypatch):
    _patch_empty(monkeypatch)
    reply, _ = w._route({"text": "@tokopedia"})
    assert "Cards" in reply


# --- freetext helpers ---

def test_is_bare_amount_and_month():
    assert freetext.is_bare_amount("222")
    assert not freetext.is_bare_amount("222 Lunch")
    assert freetext.is_bare_month("sep26")
    assert not freetext.is_bare_month("lunch")
