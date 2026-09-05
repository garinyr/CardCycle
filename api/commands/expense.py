"""api/commands/expense.py — expense entry (MVP2-ready, Option D).

Target card precedence for one message:
1. typed `@name` (active-only) — one-shot override,
2. sticky `Config.expense_card_id` (set via the chip picker) when it still
   points to an active card,
3. the global default card.

MVP1 behavior (no `@`, no sticky) is unchanged — all rows go to the default
card and the reply text is identical.
"""

from core import cardref, messages, parser, sheets
from core.formatter import bold, esc, mono, now_wib_iso, rupiah, today_wib
from api.config import CONFIG_EXPENSE_CARD_ID


def _sticky_card_id() -> int | None:
    raw = (sheets.get_config() or {}).get(CONFIG_EXPENSE_CARD_ID, "")
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _resolve_target(text: str) -> dict | None:
    """Pick the card for this message; None only when there is no card at all."""
    refs = cardref.extract_at_refs(text)
    if refs:
        card, error = cardref.command_card(text, sheets.get_cards(), sheets.get_default_card())
        if error:
            raise ValueError(error)
        return card
    default = sheets.get_default_card()
    if default is None:
        return None
    sticky = _sticky_card_id()
    if sticky is not None and sticky != default["card_id"]:
        for c in sheets.get_cards():
            if c["card_id"] == sticky and c.get("is_active"):
                return c
    return default


def handle(text: str) -> str:
    content = cardref.strip_card_refs(text)
    today = today_wib()
    rows, errors = parser.parse_expense_text(content, today)

    if not rows and not errors:
        return messages.usage("expense", "[DD/MM] <amount> <description>", "/expense 150000 Lunch")

    try:
        card = _resolve_target(text)
    except ValueError as e:
        return messages.err(str(e))
    if card is None:
        return messages.no_card()

    card_id = card["card_id"]
    first_id = sheets.allocate_ids(len(rows))
    input_at = now_wib_iso()
    to_append = []
    for i, r in enumerate(rows):
        to_append.append({
            "id": first_id + i,
            "card_id": card_id,
            "date": r["date"].isoformat(),
            "amount": r["amount"],
            "description": r["description"],
            "category": "",
            "deleted": False,
            "input_at": input_at,
        })
    sheets.append_transactions(to_append)

    lines = []
    default = sheets.get_default_card()
    if card_id != (default["card_id"] if default else None):
        name = card.get("card_name") or "card"
        lines.append(f"💳 {esc(name)}")
    for r in rows:
        amt = bold(rupiah(r["amount"]))
        date_s = mono(r["date"].strftime("%d/%m/%Y"))
        desc = esc(r["description"])
        lines.append(f"✅ {date_s} {amt} {desc}".rstrip())
    for lineno, msg in errors:
        lines.append(f"⚠️ Line {lineno}: {esc(msg)}")

    header = f"Recorded: {len(rows)} saved"
    if errors:
        header += f", {len(errors)} failed"
    return messages.info(header, *lines)
