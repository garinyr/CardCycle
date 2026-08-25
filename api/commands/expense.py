"""api/commands/expense.py — /expense single + batch."""

from core import messages, parser, sheets
from core.formatter import bold, esc, mono, now_wib_iso, rupiah, today_wib


def handle(text: str) -> str:
    today = today_wib()
    rows, errors = parser.parse_expense_text(text, today)

    if not rows and not errors:
        return messages.usage("expense", "[DD/MM] <amount> <description>", "/expense 150000 Lunch")

    card = sheets.get_default_card()
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
