import api.webhook as w
from core import prompts

CARD = {"card_id": 1, "card_name": "Test", "card_limit": 15000000, "cutoff_day": 13}


def _patch_sheets(monkeypatch):
    monkeypatch.setattr("core.sheets.get_default_card", lambda: dict(CARD))
    monkeypatch.setattr("core.sheets.read_transactions", lambda: [])


def test_statement_month_valid(monkeypatch):
    _patch_sheets(monkeypatch)
    text, markup = w._statement_month_reply("mar25")
    assert "March 2025" in text
    assert "keyboard" in markup  # typed reply re-attaches the reply-keyboard menu


def test_statement_month_invalid_retries(monkeypatch):
    _patch_sheets(monkeypatch)
    text, markup = w._statement_month_reply("garbage")
    assert text == prompts.PROMPT_STATEMENT_MONTH
    assert markup.get("force_reply") is True


def test_running_month_valid(monkeypatch):
    _patch_sheets(monkeypatch)
    text, markup = w._running_month_reply("mar25")
    assert "March 2025" in text
    assert "keyboard" in markup


def test_running_month_invalid_retries_distinct_prompt(monkeypatch):
    _patch_sheets(monkeypatch)
    text, markup = w._running_month_reply("garbage")
    assert text == prompts.PROMPT_RUNNING_MONTH
    assert markup.get("force_reply") is True


def test_statement_and_running_prompts_not_swapped(monkeypatch):
    _patch_sheets(monkeypatch)
    assert prompts.PROMPT_STATEMENT_MONTH != prompts.PROMPT_RUNNING_MONTH
    text, _ = w._statement_month_reply("zzz")
    assert text == prompts.PROMPT_STATEMENT_MONTH


def test_retry_not_dead_end(monkeypatch):
    _patch_sheets(monkeypatch)
    text1, _ = w._statement_month_reply("garbage")
    assert text1 == prompts.PROMPT_STATEMENT_MONTH
    text2, _ = w._statement_month_reply("feb26")
    assert "February 2026" in text2
