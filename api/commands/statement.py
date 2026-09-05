"""api/commands/statement.py — statement for the selected card (MVP2-ready).

Target card: `@name` wins (active cards only), else the default card.
Optional typed month / detail; otherwise the latest frozen cycle for that
card's cutoff. MVP1 behavior (no `@`) is unchanged.
"""

from core import cardref, messages, sheets
from core.cycle import cycle_label_for, prev_cycle_label
from core.formatter import parse_month_arg, render_statement, today_wib


def handle(text: str) -> str:
    today = today_wib()
    default_card = sheets.get_default_card()
    cards = sheets.get_cards() if cardref.extract_at_refs(text) else None
    card, error = cardref.command_card(text, cards, default_card)
    if card is None:
        return messages.err(error) if error else messages.no_card()

    label = None
    detail = False
    for tok in cardref.strip_card_refs(text).split():
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
