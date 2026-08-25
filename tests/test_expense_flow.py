import api.commands.expense as expense

CARD = {"card_id": 1, "card_name": "Test", "card_limit": 15000000, "cutoff_day": 13}


def _patch(monkeypatch, append_list):
    monkeypatch.setattr("core.sheets.get_default_card", lambda: dict(CARD))
    monkeypatch.setattr("core.sheets.allocate_ids", lambda count=1: 100)
    monkeypatch.setattr("core.sheets.append_transactions", append_list.append)


def test_empty_input_shows_usage():
    out = expense.handle("")
    assert "How to use" in out


def test_single(monkeypatch):
    appended = []
    _patch(monkeypatch, appended)
    out = expense.handle("150000 Lunch")
    assert "1 saved" in out
    assert len(appended) == 1 and len(appended[0]) == 1
    assert appended[0][0]["amount"] == 150000


def test_batch(monkeypatch):
    appended = []
    _patch(monkeypatch, appended)
    out = expense.handle("150000 a\n200000 b")
    assert "2 saved" in out
    assert len(appended[0]) == 2


def test_refund_negative(monkeypatch):
    appended = []
    _patch(monkeypatch, appended)
    out = expense.handle("-50000 refund")
    assert "1 saved" in out
    assert appended[0][0]["amount"] == -50000


def test_partial_failure_keeps_valid_rows(monkeypatch):
    appended = []
    _patch(monkeypatch, appended)
    out = expense.handle("150000 ok\nnot an amount here")
    assert "1 saved" in out
    assert "1 failed" in out
    assert len(appended[0]) == 1
    assert appended[0][0]["amount"] == 150000
