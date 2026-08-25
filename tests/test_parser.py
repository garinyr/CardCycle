from datetime import date

import pytest

from core.parser import parse_amount, parse_expense_line, parse_expense_text


def test_parse_amount_strips_separators():
    assert parse_amount("150000") == 150000
    assert parse_amount("150.000") == 150000
    assert parse_amount("Rp150.000") == 150000
    assert parse_amount("150,000") == 150000


def test_parse_amount_invalid():
    with pytest.raises(ValueError):
        parse_amount("abc")


def test_line_with_date():
    r = parse_expense_line("14/08 500000 Monthly shopping", date(2026, 8, 23))
    assert r["date"] == date(2026, 8, 14)
    assert r["amount"] == 500000
    assert r["description"] == "Monthly shopping"


def test_line_without_date_uses_today():
    r = parse_expense_line("150000 Lunch", date(2026, 8, 23))
    assert r["date"] == date(2026, 8, 23)
    assert r["amount"] == 150000
    assert r["description"] == "Lunch"


def test_line_with_year():
    r = parse_expense_line("14/08/2025 1000 x", date(2026, 8, 23))
    assert r["date"] == date(2025, 8, 14)


def test_line_invalid_date():
    with pytest.raises(ValueError):
        parse_expense_line("32/13 1000 x", date(2026, 8, 23))


def test_batch_collects_errors():
    text = "150000 ok\nbad no amount\n14/08 500000 groceries"
    rows, errors = parse_expense_text(text, date(2026, 8, 23))
    assert len(rows) == 2
    assert len(errors) == 1
