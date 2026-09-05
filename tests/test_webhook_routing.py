import api.webhook as w
from core import menu, prompts

CARD = {"card_id": 1, "card_name": "Test", "card_limit": 15000000, "cutoff_day": 13, "is_active": True}


def _patch_sheets(monkeypatch):
    monkeypatch.setattr("core.sheets.get_default_card", lambda: dict(CARD))
    monkeypatch.setattr("core.sheets.get_cards", lambda: [])
    monkeypatch.setattr("core.sheets.get_config", lambda: {})
    monkeypatch.setattr("core.sheets.read_transactions", lambda: [])
    monkeypatch.setattr("core.sheets.allocate_ids", lambda count=1: 1)
    monkeypatch.setattr("core.sheets.append_transactions", lambda rows: None)
    monkeypatch.setattr("core.sheets.update_card_limit", lambda cid, v: None)


# 1. reply to a ForceReply prompt → handler
def test_route_prompt_match_expense(monkeypatch):
    _patch_sheets(monkeypatch)
    msg = {"text": "150000 Lunch", "reply_to_message": {"text": prompts.PROMPT_EXPENSE_INPUT}}
    reply, markup = w._route(msg)
    assert "1 saved" in reply
    assert "keyboard" in markup


# 2. menu label tap → feature entry flow
def test_route_menu_label_statement(monkeypatch):
    _patch_sheets(monkeypatch)
    msg = {"text": menu.BTN_STATEMENT}
    reply, markup = w._route(msg)
    assert "Statement" in reply
    assert "inline_keyboard" in markup


def test_route_menu_label_expense_forces_reply(monkeypatch):
    _patch_sheets(monkeypatch)
    msg = {"text": menu.BTN_EXPENSE}
    reply, markup = w._route(msg)
    assert reply == prompts.PROMPT_EXPENSE_INPUT
    assert markup.get("force_reply") is True


# 3. direct numeric expense entry (no button tap)
def test_route_direct_expense(monkeypatch):
    _patch_sheets(monkeypatch)
    msg = {"text": "50000 kopi"}
    reply, _ = w._route(msg)
    assert "1 saved" in reply


# 4. legacy slash → redirect (never silent)
def test_route_slash_redirect(monkeypatch):
    monkeypatch.setattr("core.sheets.get_config", lambda: {})
    msg = {"text": "/statement"}
    reply, markup = w._route(msg)
    assert reply == w.SLASH_REDIRECT
    assert "keyboard" in markup


# /start and /help show the menu instead of the redirect
from core import menu as menu_mod


def test_route_start_shows_menu(monkeypatch):
    monkeypatch.setattr("core.sheets.get_config", lambda: {})
    msg = {"text": "/start"}
    reply, markup = w._route(msg)
    assert reply == menu_mod.menu_text()
    assert "keyboard" in markup


def test_route_start_with_payload_shows_menu(monkeypatch):
    monkeypatch.setattr("core.sheets.get_config", lambda: {})
    msg = {"text": "/start ref-123"}
    reply, _ = w._route(msg)
    assert reply == menu_mod.menu_text()


def test_route_help_slash_shows_menu(monkeypatch):
    monkeypatch.setattr("core.sheets.get_config", lambda: {})
    msg = {"text": "/help"}
    reply, _ = w._route(msg)
    assert reply == menu_mod.menu_text()


# 5. fallback
def test_route_fallback(monkeypatch):
    monkeypatch.setattr("core.sheets.get_config", lambda: {})
    msg = {"text": "asdfghjkl"}
    reply, markup = w._route(msg)
    assert reply == w.FALLBACK
    assert "keyboard" in markup


def test_route_statement_month_retry_on_invalid():
    msg = {"text": "not-a-month", "reply_to_message": {"text": prompts.PROMPT_STATEMENT_MONTH}}
    reply, markup = w._route(msg)
    assert reply == prompts.PROMPT_STATEMENT_MONTH
    assert markup.get("force_reply") is True
