"""api/commands/cards.py — card management (choose-card-first, reply-free input).

Cards view → pick a card → its action menu (⭐ Make main / 🎯 Limit /
📅 Cutoff). Add/Limit/Cutoff ask for a typed value in a **plain** message and
record a pending context (`core.pending`); the router consumes the next free
text and calls `limit_reply` / `cutoff_reply` / `start_add` here. `@name` stays
as an optional one-shot override in the typed value.
"""

import re

from core import cardref, messages, parser, pending, sheets
from core.formatter import bold, esc, rupiah

_CUTOFF_RE = re.compile(r"(?i)cutoff\s+(\d{1,2})")


def _line(c: dict, default_id: int | None) -> str:
    name = esc(c.get("card_name") or "?")
    limit = c.get("card_limit")
    cutoff = c.get("cutoff_day")
    flags = []
    if c["card_id"] == default_id:
        flags.append("⭐ default")
    if not c.get("is_active"):
        flags.append("inactive")
    detail = f"limit {rupiah(limit)} · cutoff {cutoff}" if cutoff else f"limit {rupiah(limit)}"
    suffix = f"  ({', '.join(flags)})" if flags else ""
    return f"{c['card_id']}. {name} — {detail}{suffix}"


def view() -> str:
    """Card list + flags. Empty list → error prompting to Add."""
    cards = sheets.get_cards()
    if not cards:
        return messages.err("No cards yet — tap ➕ Add card to create one.")
    default = sheets.get_default_card()
    default_id = default["card_id"] if default else None
    return messages.info("Your cards", *[_line(c, default_id) for c in cards])


def describe(card_id: int) -> str:
    """Single-card header shown when its action menu opens."""
    card = sheets.get_card(card_id)
    if card is None:
        return messages.err("Card not found.")
    default = sheets.get_default_card()
    return _line(card, default["card_id"] if default else None)


def set_main(card_id: int) -> str:
    """Make `card_id` the default card (pure-tap action)."""
    card = sheets.get_card(card_id)
    if card is None:
        return messages.err("Card not found.")
    sheets.set_config("default_card_id", str(card_id))
    return messages.ok(f"Default card: {card.get('card_name')}")


# --- add (typed, then confirmed before any write) ---

def _parse_add(text: str) -> tuple[str, int, int]:
    """'Name amount [cutoff N]' → (name, limit, cutoff). Raise ValueError."""
    m = _CUTOFF_RE.search(text)
    cutoff = 13
    rest = text
    if m:
        day = int(m.group(1))
        if not 1 <= day <= 28:
            raise ValueError("cutoff must be 1–28")
        cutoff = day
        rest = text[:m.start()].strip()

    tokens = rest.split()
    amount_idx = None
    amount = None
    for i, tok in enumerate(tokens):
        try:
            amount = parser.parse_amount(tok)
            amount_idx = i
            break
        except ValueError:
            continue
    if amount_idx is None:
        raise ValueError("amount is missing — format: Name amount [cutoff N]")
    if amount <= 0:
        raise ValueError("limit must be a positive number")
    name = " ".join(tokens[:amount_idx] + tokens[amount_idx + 1:]).strip()
    if not name:
        raise ValueError("name is missing — format: Name amount [cutoff N]")

    existing = sheets.get_cards()
    if any(str(c.get("card_name", "")).strip().lower() == name.lower() for c in existing):
        raise ValueError(f"a card named '{name}' already exists")
    return name, amount, cutoff


def start_add(text: str):
    """Consume the typed Add text → error message, or confirm prompt + data."""
    try:
        name, amount, cutoff = _parse_add(text)
    except ValueError as e:
        return messages.err(str(e)), None
    pending.save_draft(name, amount, cutoff)
    preview = messages.info(
        "Add this card?",
        f"{esc(name)} — limit {bold(rupiah(amount))} · cutoff {cutoff}",
    )
    return preview, None  # markup added by webhook (✅/✖️)


def confirm_add(confirmed: bool) -> str:
    """Finish the Add flow: write only when confirmed; always clear draft."""
    draft = pending.draft()
    pending.clear_pending()
    if not confirmed or draft is None:
        return messages.info("Add card cancelled.")
    name, amount, cutoff = draft
    card_id = sheets.allocate_card_id()
    sheets.add_card(card_id, name, amount, cutoff)
    return messages.ok(
        f"Card added: {name}",
        f"id {card_id} · limit {bold(rupiah(amount))} · cutoff {cutoff}",
    )


# --- limit / cutoff (value only; card from pending target or @name) ---

def _target_for_value(text: str) -> dict:
    refs = cardref.extract_at_refs(text)
    if refs:
        card, error = cardref.command_card(text, sheets.get_cards(), sheets.get_default_card())
        if error:
            raise ValueError(error)
        return card
    p = pending.pending()
    if p is not None and p[0] in ("limit", "cutoff") and p[1] is not None:
        card = sheets.get_card(p[1])
        if card is not None and card.get("is_active"):
            return card
    card = sheets.get_default_card()
    if card is None:
        raise ValueError("No card set up yet.")
    return card


def limit_reply(text: str) -> str:
    clean = cardref.strip_card_refs(text).strip()
    if not clean:
        return messages.err("amount is missing")
    try:
        amount = parser.parse_amount(clean)
    except ValueError as e:
        return messages.err(str(e))
    if amount <= 0:
        return messages.err("limit must be a positive number")
    try:
        card = _target_for_value(text)
    except ValueError as e:
        return messages.err(str(e))
    old = card.get("card_limit")
    sheets.update_card_limit(card["card_id"], amount)
    name = card.get("card_name") or "card"
    return messages.ok(
        f"Limit {name} updated",
        f"{bold(rupiah(old) if old else '-')} → {bold(rupiah(amount))}",
    )


def cutoff_reply(text: str) -> str:
    clean = cardref.strip_card_refs(text).strip()
    if not clean:
        return messages.err("day is missing")
    try:
        day = int(clean)
    except ValueError:
        return messages.err(f"invalid day: {clean}")
    if not 1 <= day <= 28:
        return messages.err("cutoff must be 1–28")
    try:
        card = _target_for_value(text)
    except ValueError as e:
        return messages.err(str(e))
    sheets.update_card_cutoff(card["card_id"], day)
    name = card.get("card_name") or "card"
    return messages.ok(f"Cutoff {name} updated", f"cutoff day → {day}")
