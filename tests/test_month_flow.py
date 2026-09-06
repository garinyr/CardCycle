"""tests/test_month_flow.py — month input via reply-free pending (stmt/run).

The typed-month flow no longer uses ForceReply replies: tapping 📅 Other month
opens a pending `month` action; free text is consumed only while fresh.
"""

import api.webhook as w
from core import pending as p
from core import prompts

CARD = {"card_id": 1, "card_name": "Test", "card_limit": 15000000, "cutoff_day": 13, "is_active": True}


def _pending_cfg(action, origin, card=1):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    ts = datetime.now(ZoneInfo("Asia/Jakarta")).isoformat(timespec="seconds")
    return {"app.pending_action": action, "app.pending_ts": ts, "app.edit_card_id": str(card)}


def _patch(monkeypatch, cfg, txns=None):
    monkeypatch.setattr("core.sheets.get_default_card", lambda: dict(CARD))
    monkeypatch.setattr("core.sheets.get_cards", lambda: [dict(CARD)])
    monkeypatch.setattr("core.sheets.get_card", lambda cid: dict(CARD))
    monkeypatch.setattr("core.sheets.get_config", lambda: cfg)
    monkeypatch.setattr("core.sheets.upsert_config", lambda k, v: cfg.__setitem__(k, v))
    monkeypatch.setattr("core.sheets.read_transactions", lambda: txns or [])


def test_month_valid_routes_to_statement(monkeypatch):
    cfg = _pending_cfg(p.ACTION_MONTH, p.ORIGIN_STMT)
    _patch(monkeypatch, cfg)
    monkeypatch.setattr("api.commands.statement.today_wib", lambda: __import__("datetime").date(2026, 9, 5))
    reply, _ = w._route({"text": "sep26"})
    assert "September 2026" in reply
    assert cfg.get("app.pending_action") == ""


def test_month_valid_routes_to_running(monkeypatch):
    cfg = _pending_cfg(p.ACTION_MONTH, p.ORIGIN_RUN)
    _patch(monkeypatch, cfg)
    monkeypatch.setattr("api.commands.running.today_wib", lambda: __import__("datetime").date(2026, 9, 5))
    reply, _ = w._route({"text": "sep26"})
    assert "Running" in reply
    assert cfg.get("app.pending_action") == ""


def test_month_invalid_keeps_pending(monkeypatch):
    cfg = _pending_cfg(p.ACTION_MONTH, p.ORIGIN_STMT)
    _patch(monkeypatch, cfg)
    reply, markup = w._route({"text": "garbage"})
    assert "Invalid month" in reply
    assert cfg.get("app.pending_action") == p.ACTION_MONTH  # stays for retype
    assert "cards:cancel" in str(markup)


def test_statement_and_running_prompts_distinct():
    assert prompts.PROMPT_STATEMENT_MONTH != prompts.PROMPT_RUNNING_MONTH


def test_no_pending_month_text_generic_error(monkeypatch):
    _patch(monkeypatch, {})
    reply, _ = w._route({"text": "sep26"})
    assert reply == w.FALLBACK
