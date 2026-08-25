"""core/utilization.py — utilization percent + band status."""

_BANDS: list[tuple[float, str]] = [
    (10, "Excellent"),
    (30, "Good"),
    (50, "Watch"),
    (75, "High"),
    (100, "Very High"),
]


def utilization_percent(total_spend: float, card_limit: float) -> float | None:
    """Return (spend / limit) * 100, or None if limit is unset (<= 0)."""
    if card_limit is None or card_limit <= 0:
        return None
    return (total_spend / card_limit) * 100


def band_for(percent: float) -> str:
    """Map a percent to one of 6 band labels. >100 = Over Limit."""
    if percent > 100:
        return "Over Limit"
    for threshold, label in _BANDS:
        if percent <= threshold:
            return label
    return "Over Limit"
