"""api/commands/summary.py — 📊 Summary: all active cards at a glance (MVP2).

Read-only: one block per active card with the *running* cycle's spend, that
card's limit, utilization % and band. Reads Cards + Transactions once per
invocation (call budget §10.9).
"""

from datetime import date

from core import messages, sheets
from core.cycle import cycle_label_for, cycle_start_end
from core.formatter import BAND_EMOJI, band_for, esc, rupiah, today_wib
from core.utilization import utilization_percent


def handle() -> str:
    cards = sheets.get_cards()
    active = [c for c in cards if c.get("is_active")]
    if not active:
        return messages.err("No active cards yet — add one via 🗂 Cards.")

    today = today_wib()
    transactions = sheets.read_transactions()
    default = sheets.get_default_card()
    default_id = default["card_id"] if default else None

    lines = []
    for c in active:
        cutoff = c.get("cutoff_day") or 13
        label = cycle_label_for(today, cutoff)
        start, end = cycle_start_end(label, cutoff)
        total = sum(
            t["amount"] or 0
            for t in transactions
            if t.get("card_id") == c["card_id"]
            and not t.get("deleted")
            and t.get("date")
            and start <= date.fromisoformat(t["date"]) <= end
        )
        limit = c.get("card_limit")
        pct = utilization_percent(total, limit)
        if pct is None:
            status = "Limit not set"
        else:
            band = band_for(pct)
            status = f"{pct:.1f}%  {BAND_EMOJI.get(band, '')} {band}"
        name = esc(c.get("card_name") or "?")
        marker = " ⭐" if c["card_id"] == default_id else ""
        lines.append(f"{name}{marker}: {rupiah(total)} / {rupiah(limit)} ({status})")
    return messages.info("Summary — running cycle per card", *lines)
