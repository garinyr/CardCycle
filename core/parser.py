"""core/parser.py — parse /expense input (single + batch).

Per-line format: `[DD/MM[/YYYY]] <amount> <description>`.
- date is optional; falls back to `today`.
- amount: whole rupiah (150000, 150.000, Rp150.000, 150,000); negative allowed for refund.
- description: remaining text after the amount.
"""

import re
from datetime import date

_DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$")


def parse_date(token: str, today: date) -> date | None:
    """Parse 'DD/MM[/YYYY]' relative to `today`'s year. Return None if not a date token."""
    m = _DATE_RE.match(token)
    if not m:
        return None
    day, month = int(m.group(1)), int(m.group(2))
    year = today.year
    if m.group(3):
        yy = int(m.group(3))
        year = yy + 2000 if yy < 100 else yy
    try:
        return date(year, month, day)
    except ValueError:
        raise ValueError(f"invalid date: {token}")


def parse_amount(token: str) -> int:
    """Parse a whole rupiah amount (negative allowed for refund).

    Accepts 150000, 150.000, 1.500.000, Rp150.000, -150000.
    Rejects decimals (150,5 / 150.50) — never silently corrupt the number.
    """
    t = token.strip().replace("Rp", "").replace("rp", "").strip()
    neg = t.startswith("-")
    if neg:
        t = t[1:].strip()
    if not t:
        raise ValueError(f"invalid amount: {token}")
    if "." in t and "," in t:
        raise ValueError(f"invalid amount (mixed separators): {token}")
    sep = "." if "." in t else ("," if "," in t else None)
    if sep is not None:
        groups = t.split(sep)
        # every group after the first must be exactly 3 digits (thousands); otherwise decimal/wrong
        if any(len(g) != 3 for g in groups[1:]):
            raise ValueError(f"invalid amount (not whole thousands): {token}")
        if not (1 <= len(groups[0]) <= 3):
            raise ValueError(f"invalid amount: {token}")
        t = "".join(groups)
    if not t.isdigit():
        raise ValueError(f"invalid amount: {token}")
    value = int(t)
    return -value if neg else value


def parse_expense_line(line: str, today: date) -> dict:
    """Parse one /expense line → {date, amount, description}. Raise ValueError on failure."""
    line = line.strip()
    if not line:
        raise ValueError("empty line")

    tokens = line.split()
    date_ = today

    if _DATE_RE.match(tokens[0]):
        date_ = parse_date(tokens[0], today)
        rest = tokens[1:]
    else:
        rest = tokens

    if not rest:
        raise ValueError("amount is missing")

    amount = parse_amount(rest[0])
    description = " ".join(rest[1:]).strip()

    return {"date": date_, "amount": amount, "description": description}


def parse_expense_text(text: str, today: date) -> tuple[list[dict], list[tuple[int, str]]]:
    """Parse multi-line /expense. Return (rows, errors) with error=(line_no, msg)."""
    rows: list[dict] = []
    errors: list[tuple[int, str]] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            rows.append(parse_expense_line(raw, today))
        except ValueError as e:
            errors.append((i, str(e)))
    return rows, errors
