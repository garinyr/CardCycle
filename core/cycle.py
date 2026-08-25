"""core/cycle.py — cutoff logic. cycle_label is computed ON-READ, never stored."""

import calendar
from datetime import date


def cycle_label_for(d: date, cutoff_day: int) -> str:
    """Cycle label 'YYYY-MM' for a transaction date.

    day <= cutoff_day  -> falls in the current month's cycle.
    day >  cutoff_day  -> falls in the next month's cycle (Dec -> Jan rollover).
    """
    if d.day <= cutoff_day:
        return f"{d.year:04d}-{d.month:02d}"
    if d.month == 12:
        return f"{d.year + 1:04d}-01"
    return f"{d.year:04d}-{d.month + 1:02d}"


def prev_cycle_label(label: str) -> str:
    """'YYYY-MM' -> previous month's cycle label (Jan -> Dec of previous year)."""
    y, m = int(label[:4]), int(label[5:7])
    if m == 1:
        return f"{y - 1:04d}-12"
    return f"{y:04d}-{m - 1:02d}"


def _month_before(y: int, m: int) -> tuple[int, int]:
    if m == 1:
        return y - 1, 12
    return y, m - 1


def cycle_start_end(label: str, cutoff_day: int) -> tuple[date, date]:
    """Inclusive range (start, end) for cycle 'YYYY-MM'.

    Cycle 'YYYY-MM' spans (previous month, cutoff_day+1) .. (this month, cutoff_day).
    """
    y, m = int(label[:4]), int(label[5:7])
    end = date(y, m, min(cutoff_day, calendar.monthrange(y, m)[1]))
    py, pm = _month_before(y, m)
    last = calendar.monthrange(py, pm)[1]
    start = date(py, pm, min(cutoff_day + 1, last))
    return start, end
