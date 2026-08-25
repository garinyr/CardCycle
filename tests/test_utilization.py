import pytest

from core.utilization import band_for, utilization_percent


def test_percent():
    assert utilization_percent(2150000, 15000000) == pytest.approx(14.333, rel=1e-3)


def test_percent_no_limit():
    assert utilization_percent(100, 0) is None
    assert utilization_percent(100, None) is None


def test_band_boundaries():
    assert band_for(0) == "Excellent"
    assert band_for(10) == "Excellent"
    assert band_for(10.1) == "Good"
    assert band_for(30) == "Good"
    assert band_for(50) == "Watch"
    assert band_for(75) == "High"
    assert band_for(100) == "Very High"
    assert band_for(100.1) == "Over Limit"
