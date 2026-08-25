"""api/commands/limit.py — /limit (view) + /limit <amount> (update)."""

from core import messages, parser, sheets
from core.formatter import bold, rupiah


def handle(text: str) -> str:
    card = sheets.get_default_card()
    if card is None:
        return messages.no_card()

    if not text.strip():
        limit = card.get("card_limit")
        name = card.get("card_name") or "card"
        return messages.info(f"Limit {name}", bold(rupiah(limit) if limit else "Not set"))

    try:
        new_limit = parser.parse_amount(text)
    except ValueError as e:
        return messages.err(str(e))

    old = card.get("card_limit")
    sheets.update_card_limit(card["card_id"], new_limit)
    name = card.get("card_name") or "card"
    return messages.ok(
        f"Limit {name} updated",
        f"{bold(rupiah(old) if old else '-')} → {bold(rupiah(new_limit))}",
    )
