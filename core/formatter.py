"""core/formatter.py — WIB clock, month names, output rendering."""

import html
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from core.cycle import cycle_start_end
from core.utilization import band_for, utilization_percent

TZ = ZoneInfo("Asia/Jakarta")

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}

_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

DIVIDER = "━━━━━━━━━━━━━━━━━━━━"

# Utilization status emoji, aligned with band labels in core/utilization.py.
BAND_EMOJI = {
    "Excellent": "🟢",
    "Good": "🟢",
    "Watch": "🟡",
    "High": "🟠",
    "Very High": "🔴",
    "Over Limit": "⛔",
}


def esc(text) -> str:
    """Escape text for parse_mode=HTML (user content, error messages)."""
    return html.escape(str(text), quote=False)


def bold(text) -> str:
    """Bold HTML — text is auto-escaped."""
    return f"<b>{esc(text)}</b>"


def mono(text) -> str:
    """Monospace (inline code) HTML — text is auto-escaped."""
    return f"<code>{esc(text)}</code>"


def block(*lines: str) -> str:
    """Join lines into one message (trim trailing newline only)."""
    return "\n".join(lines).strip("\n")


def today_wib() -> date:
    return datetime.now(TZ).date()


def now_wib_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def rupiah(n) -> str:
    """Format an integer amount as rupiah, e.g. -Rp 1.041.741."""
    v = int(n or 0)
    sign = "-" if v < 0 else ""
    return f"{sign}Rp {abs(v):,}".replace(",", ".")


def month_name(label: str) -> str:
    """'YYYY-MM' -> 'August 2026'."""
    y, m = int(label[:4]), int(label[5:7])
    return f"{MONTH_NAMES[m]} {y}"


def _fmt_date(d: date) -> str:
    return f"{d.day} {MONTH_NAMES[d.month]} {d.year}"


def parse_month_arg(token: str, today: date) -> str | None:
    """Parse a month name/abbr (+ optional 2/4-digit year) → 'YYYY-MM', else None.

    2-digit year uses the same convention as parse_date: 25 → 2025, 99 → 2099.
    """
    t = token.strip().lower()
    m = re.match(r"^([a-z]+)(\d{2}|\d{4})?$", t)
    if m:
        name, yr = m.group(1), m.group(2)
        month = None
        for num, full in MONTH_NAMES.items():
            if name == full.lower():
                month = num
                break
        if month is None:
            month = _MONTH_ABBR.get(name)
        if month is not None:
            year = today.year
            if yr:
                yy = int(yr)
                year = 2000 + yy if len(yr) == 2 else yy
            return f"{year:04d}-{month:02d}"
    if t.isdigit() and 1 <= int(t) <= 12:
        return f"{today.year:04d}-{int(t):02d}"
    return None


def render_statement(card: dict, transactions: list[dict], label: str, detail: bool = False, title: str = "Statement") -> str:
    cutoff = card.get("cutoff_day") or 13
    start, end = cycle_start_end(label, cutoff)

    txs = [
        t for t in transactions
        if t.get("card_id") == card.get("card_id")
        and not t.get("deleted")
        and t.get("date")
        and start <= date.fromisoformat(t["date"]) <= end
    ]
    total = sum(t["amount"] or 0 for t in txs)
    limit = card.get("card_limit")
    card_name = card.get("card_name") or "Card"

    # Key-value block uses <pre> so columns align (spaces don't collapse in HTML).
    kv = [
        f"Total spend      : {rupiah(total)}",
        f"Transactions     : {len(txs)}",
        f"Card limit       : {rupiah(limit) if limit else '-'}",
    ]
    pct = utilization_percent(total, limit) if limit else None
    if pct is None:
        kv.append("Utilization      : Limit not set")
    else:
        band = band_for(pct)
        kv.append(f"Utilization      : {pct:.1f}%  {BAND_EMOJI.get(band, '')} {band}")

    lines = [
        f"{bold(f'📄 {title}')} {esc(month_name(label))}",
        f"{mono(_fmt_date(start))} – {mono(_fmt_date(end))} · {esc(card_name)}",
        DIVIDER,
        "<pre>" + "\n".join(kv) + "</pre>",
    ]

    if detail and txs:
        rows = [
            f"- {t['date']}  {rupiah(t['amount'])}  {esc(t['description'])}".rstrip()
            for t in sorted(txs, key=lambda x: x["date"])
        ]
        lines.append("")
        lines.append("Details:")
        lines.append("<pre>" + "\n".join(rows) + "</pre>")

    return block(*lines)
