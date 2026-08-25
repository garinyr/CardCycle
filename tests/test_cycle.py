from datetime import date

from core.cycle import cycle_label_for, cycle_start_end, prev_cycle_label


def test_label_day_on_or_before_cutoff_same_month():
    assert cycle_label_for(date(2026, 8, 13), 13) == "2026-08"
    assert cycle_label_for(date(2026, 8, 1), 13) == "2026-08"


def test_label_day_after_cutoff_next_month():
    assert cycle_label_for(date(2026, 8, 14), 13) == "2026-09"


def test_label_december_rollover():
    assert cycle_label_for(date(2026, 12, 14), 13) == "2027-01"


def test_prev_cycle_label():
    assert prev_cycle_label("2026-09") == "2026-08"
    assert prev_cycle_label("2026-01") == "2025-12"
    assert prev_cycle_label("2027-02") == "2027-01"


def test_start_end_cutoff_13():
    start, end = cycle_start_end("2026-02", 13)
    assert start == date(2026, 1, 14)
    assert end == date(2026, 2, 13)


def test_start_end_january_rollover():
    start, end = cycle_start_end("2026-01", 13)
    assert start == date(2025, 12, 14)
    assert end == date(2026, 1, 13)
