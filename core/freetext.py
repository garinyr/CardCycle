"""core/freetext.py — targeted help for free text that has no destination.

Pure helpers used by the webhook's fallback path. `suggest(text)` returns a
short, useful hint for the most likely intention (bare amount, bare month,
@card, etc.) or None, in which case the caller shows the generic fallback.
"""

from core.formatter import parse_month_arg, today_wib


def is_bare_amount(text: str) -> bool:
    """True when the whole message is just a number (no description)."""
    t = text.strip().replace(".", "").replace(",", "")
    return bool(t) and t.isdigit()


def is_bare_month(text: str) -> bool:
    """True when the text parses as a month token (sep26, november, 9 …)."""
    return parse_month_arg(text.strip(), today_wib()) is not None


def starts_with_card_ref(text: str) -> bool:
    return text.strip().startswith("@")


def suggest(text: str) -> str | None:
    """One-line hint for untargeted free text, else None."""
    if is_bare_amount(text):
        return "That looks like an amount — tap 💳 Expense to record it, or confirm below if the bot asked."
    if is_bare_month(text):
        return "That looks like a month — tap 📄 Statement / 📊 Running, then pick it (or type @card <month> in the month prompt)."
    if starts_with_card_ref(text):
        return "Card names only work inside a card/menu flow — tap 🗂 Cards and pick the card."
    return None
