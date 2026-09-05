"""api/commands/limit.py — limit view/update for the selected card (MVP2-ready).

Target card: `@name` wins (active cards only), else the default card.
No `@` + no amount = view; with amount = update that card's limit.
MVP1 behavior (default card, no `@`) is unchanged.
"""

from core import cardref, messages, parser, sheets
from core.formatter import bold, rupiah


def handle(text: str) -> str:
    default_card = sheets.get_default_card()
    cards = sheets.get_cards() if cardref.extract_at_refs(text) else None
    card, error = cardref.command_card(text, cards, default_card)
    if card is None:
        return messages.err(error) if error else messages.no_card()

    clean = cardref.strip_card_refs(text).strip()
    name = card.get("card_name") or "card"

    if not clean:
        limit = card.get("card_limit")
        return messages.info(f"Limit {name}", bold(rupiah(limit) if limit else "Not set"))

    try:
        new_limit = parser.parse_amount(clean)
    except ValueError as e:
        return messages.err(str(e))

    old = card.get("card_limit")
    sheets.update_card_limit(card["card_id"], new_limit)
    return messages.ok(
        f"Limit {name} updated",
        f"{bold(rupiah(old) if old else '-')} → {bold(rupiah(new_limit))}",
    )
