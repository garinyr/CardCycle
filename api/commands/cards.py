"""api/commands/cards.py — card management (MVP2, choose-card-first flows).

`view()` renders the card list (used by the 🗂 Cards button). The per-card
actions are entered from the inline rows under the view:

- `cards:main:<card_id>` — make a card the default (pure tap, no typing).
- `cards:lmt:<card_id>` / `cards:cut:<card_id>` — choose the card by tap, then
  the bot stores it as the pending edit target (`Config.cards.edit_card_id`)
  and asks for the **value only**. `limit_reply`/`cutoff_reply` read the
  pending target, clear it after use, and keep `@name` only as an optional
  one-shot override.
- `cards:add` — still typed (`Name amount [cutoff N]`), a new card has no row.

Everything stays stateless-safe: the chosen card travels through the pending
Config key, never through memory.
"""

import re

from core import cardref, messages, parser, sheets
from core.formatter import bold, esc, rupiah
from api.config import CONFIG_CARDS_EDIT_CARD_ID

_CUTOFF_RE = re.compile(r"(?i)cutoff\s+(\d{1,2})")


def _pending_card_id() -> int | None:
    raw = (sheets.get_config() or {}).get(CONFIG_CARDS_EDIT_CARD_ID, "")
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _clear_pending() -> None:
    sheets.upsert_config(CONFIG_CARDS_EDIT_CARD_ID, "")


def view() -> str:
    """Card list + flags. Empty list → error prompting to Add."""
    cards = sheets.get_cards()
    if not cards:
        return messages.err("No cards yet — tap ➕ Add card to create one.")
    default = sheets.get_default_card()
    default_id = default["card_id"] if default else None

    lines = []
    for c in cards:
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
        lines.append(f"{c['card_id']}. {name} — {detail}{suffix}")
    return messages.info("Your cards", *lines)


def set_main(card_id: int) -> str:
    """Make `card_id` the default card (pure-tap action)."""
    card = sheets.get_card(card_id)
    if card is None:
        return messages.err("Card not found.")
    sheets.set_config("default_card_id", str(card_id))
    return messages.ok(f"Default card: {card.get('card_name')}")


# --- add ---

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


def add_reply(text: str) -> str:
    try:
        name, amount, cutoff = _parse_add(text)
    except ValueError as e:
        return messages.err(str(e))
    card_id = sheets.allocate_card_id()
    sheets.add_card(card_id, name, amount, cutoff)
    return messages.ok(
        f"Card added: {name}",
        f"id {card_id} · limit {bold(rupiah(amount))} · cutoff {cutoff}",
    )


# --- limit / cutoff (value only; card from pending target or @name) ---

def _target_for_value(text: str) -> dict:
    """Card to edit: optional @name wins; else pending target; else default."""
    refs = cardref.extract_at_refs(text)
    if refs:
        card, error = cardref.command_card(text, sheets.get_cards(), sheets.get_default_card())
        if error:
            raise ValueError(error)
        return card
    pending = _pending_card_id()
    if pending is not None:
        card = sheets.get_card(pending)
        if card is not None and card.get("is_active"):
            return card
    card = sheets.get_default_card()
    if card is None:
        raise ValueError("No card set up yet.")
    return card


def _parse_limit(text: str):
    clean = cardref.strip_card_refs(text).strip()
    if not clean:
        raise ValueError("amount is missing")
    amount = parser.parse_amount(clean)
    if amount <= 0:
        raise ValueError("limit must be a positive number")
    return _target_for_value(text), amount


def limit_reply(text: str) -> str:
    try:
        card, amount = _parse_limit(text)
    except ValueError as e:
        _clear_pending()
        return messages.err(str(e))
    _clear_pending()
    old = card.get("card_limit")
    sheets.update_card_limit(card["card_id"], amount)
    name = card.get("card_name") or "card"
    return messages.ok(
        f"Limit {name} updated",
        f"{bold(rupiah(old) if old else '-')} → {bold(rupiah(amount))}",
    )


def _parse_cutoff(text: str):
    clean = cardref.strip_card_refs(text).strip()
    if not clean:
        raise ValueError("day is missing")
    try:
        day = int(clean)
    except ValueError:
        raise ValueError(f"invalid day: {clean}")
    if not 1 <= day <= 28:
        raise ValueError("cutoff must be 1–28")
    return _target_for_value(text), day


def cutoff_reply(text: str) -> str:
    try:
        card, day = _parse_cutoff(text)
    except ValueError as e:
        _clear_pending()
        return messages.err(str(e))
    _clear_pending()
    sheets.update_card_cutoff(card["card_id"], day)
    name = card.get("card_name") or "card"
    return messages.ok(f"Cutoff {name} updated", f"cutoff day → {day}")
