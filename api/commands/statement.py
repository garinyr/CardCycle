"""api/commands/statement.py — /statement [month] [detail]."""

from core import messages, sheets
from core.cycle import cycle_label_for, prev_cycle_label
from core.formatter import parse_month_arg, render_statement, today_wib


def handle(text: str) -> str:
    today = today_wib()
    card = sheets.get_default_card()
    if card is None:
        return messages.no_card()

    label = None
    detail = False
    for tok in text.split():
        t = tok.strip().lower()
        if t in ("detail", "d"):
            detail = True
            continue
        if label is None:
            label = parse_month_arg(tok, today)

    if label is None:
        cutoff = card.get("cutoff_day") or 13
        label = prev_cycle_label(cycle_label_for(today, cutoff))

    transactions = sheets.read_transactions()
    return render_statement(card, transactions, label, detail=detail)
