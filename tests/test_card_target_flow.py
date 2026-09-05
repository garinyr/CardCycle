"""tests/test_card_target_flow.py — MVP2 card targeting in statement/running/limit.

Proves two-card isolation: each command renders/updates only the targeted card,
and the no-`@` path keeps MVP1 behavior (default card, lazy sheets calls).
"""

import api.commands.running as running
import api.commands.statement as statement
from core import sheets

BNI = {"card_id": 1, "card_name": "BNI Mastercard", "card_limit": 15000000, "cutoff_day": 13, "is_active": True}
TOKOPEDIA = {"card_id": 2, "card_name": "Tokopedia Card", "card_limit": 8000000, "cutoff_day": 27, "is_active": True}

# 20 Aug 2026 is inside BNI's September cycle (14 Aug–13 Sep) but NOT
# Tokopedia's (28 Aug–27 Sep). 20 Sep is inside Tokopedia's September cycle
# but not BNI's. So the totals discriminate per card.
TXNS = [
    {"id": 1, "card_id": 1, "date": "2026-08-20", "amount": 100000, "description": "BNI only", "deleted": False},
    {"id": 2, "card_id": 2, "date": "2026-09-20", "amount": 200000, "description": "Tokopedia only", "deleted": False},
]


def _patch(monkeypatch, cards=None, default=None, txns=None):
    monkeypatch.setattr(sheets, "get_cards", lambda: cards or [])
    monkeypatch.setattr(sheets, "get_default_card", lambda: default)
    monkeypatch.setattr(sheets, "read_transactions", lambda: txns if txns is not None else TXNS)


# --- statement: per-card isolation + default fallback ---

def test_statement_targets_card_via_at(monkeypatch):
    _patch(monkeypatch, cards=[BNI, TOKOPEDIA], default=BNI)
    out = statement.handle("@tokopedia sep26")
    assert "Tokopedia Card" in out and "September 2026" in out
    assert "Rp 200.000" in out and "Rp 100.000" not in out


def test_statement_no_at_uses_default_card(monkeypatch):
    # get_cards is NOT called without an '@' (lazy) — prove by raising.
    def boom():
        raise RuntimeError("get_cards should not be called")

    monkeypatch.setattr(sheets, "get_cards", boom)
    monkeypatch.setattr(sheets, "get_default_card", lambda: BNI)
    monkeypatch.setattr(sheets, "read_transactions", lambda: TXNS)
    out = statement.handle("sep26")
    assert "BNI Mastercard" in out
    assert "Rp 100.000" in out and "Rp 200.000" not in out


def test_running_targets_card_via_at(monkeypatch):
    _patch(monkeypatch, cards=[BNI, TOKOPEDIA], default=BNI)
    out = running.handle("@tokopedia sep26")
    assert "Running" in out and "Tokopedia Card" in out
    assert "Rp 200.000" in out and "Rp 100.000" not in out


# --- error paths ---

def test_ambiguous_ref_lists_candidates(monkeypatch):
    other_bni = {"card_id": 9, "card_name": "BNI Xtra", "card_limit": 5000000, "cutoff_day": 13, "is_active": True}
    _patch(monkeypatch, cards=[BNI, other_bni], default=BNI, txns=[])
    out = statement.handle("@bni sep26")
    assert "Ambiguous @bni" in out and "BNI Mastercard" in out and "BNI Xtra" in out


def test_unknown_ref_lists_active_cards(monkeypatch):
    _patch(monkeypatch, cards=[BNI, TOKOPEDIA], default=BNI, txns=[])
    out = statement.handle("@nope sep26")
    assert "Unknown card: @nope" in out
    assert "Available" in out and "Tokopedia Card" in out


def test_multiple_refs_rejected(monkeypatch):
    _patch(monkeypatch, cards=[BNI, TOKOPEDIA], default=BNI, txns=[])
    out = statement.handle("@bni @tokopedia sep26")
    assert "Multiple @card references" in out


def test_inactive_card_not_selectable_via_at(monkeypatch):
    inactive_tok = dict(TOKOPEDIA, is_active=False)
    _patch(monkeypatch, cards=[BNI, inactive_tok], default=BNI, txns=[])
    out = statement.handle("@tokopedia sep26")
    assert "Unknown card: @tokopedia" in out


def test_no_card_at_all_shows_no_card_message(monkeypatch):
    _patch(monkeypatch, cards=[], default=None, txns=[])
    out = statement.handle("sep26")
    assert "No card" in out
