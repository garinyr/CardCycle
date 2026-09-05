"""api/commands/cards.py — card management (MVP2 P3).

`view()` renders the card list (used by the 🗂 Cards button). The action
flows (add / default / limit / cutoff) are entered from the inline action row
(`cards:<action>` callbacks in the webhook) which sends the matching prompt;
the typed reply is routed by exact-match to the `*_reply` functions below.
Target cards inside a reply are named with `@name` (default card when absent),
keeping everything stateless.
"""

import re

from core import cardref, messages, parser, sheets
from core.formatter import bold, esc, rupiah

_CUTOFF_RE = re.compile(r"(?i)cutoff\s+(\d{1,2})")


def _resolve_named_or_default(text: str) -> dict | None:
    """Card named by `@name` (active-only); falls back to the default card."""
    refs = cardref.extract_at_refs(text)
    cards = sheets.get_cards() if refs else None
    card, error = cardref.command_card(text, cards, sheets.get_default_card())
    if error:
        raise ValueError(error)
    return card


def view() -> str:
    """Card list + flags. Empty list → error prompting to Add."""
    cards = sheets.get_cards()
    if not cards:
        return messages.err("No cards yet — tap ➕ Add to create one.")
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


def add_reply(text: str):
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


# --- default ---

def _resolve_exactly(text: str) -> dict:
    """@name ref, or a bare name matched exactly/prefix/partial on active cards."""
    refs = cardref.extract_at_refs(text)
    cards = sheets.get_cards()
    if refs:
        card, error = cardref.command_card(text, cards, None)
        if error:
            raise ValueError(error)
        return card
    candidates = cardref.find_candidates(text.strip().lower(), cards)
    if len(candidates) == 1:
        return candidates[0]
    raise ValueError("Unknown or ambiguous card — type @name (e.g. @bni).")


def default_reply(text: str):
    try:
        card = _resolve_exactly(text)
    except ValueError as e:
        return messages.err(str(e))
    sheets.set_config("default_card_id", str(card["card_id"]))
    return messages.ok(f"Default card: {card.get('card_name')}")


# --- limit / cutoff (shared target + value) ---

def _limit_target(text: str):
    clean = cardref.strip_card_refs(text).strip()
    if not clean:
        raise ValueError("amount is missing")
    card = _resolve_named_or_default(text)
    amount = parser.parse_amount(clean)
    if amount <= 0:
        raise ValueError("limit must be a positive number")
    return card, amount


def limit_reply(text: str):
    try:
        card, amount = _limit_target(text)
    except ValueError as e:
        return messages.err(str(e))
    old = card.get("card_limit")
    sheets.update_card_limit(card["card_id"], amount)
    name = card.get("card_name") or "card"
    return messages.ok(
        f"Limit {name} updated",
        f"{bold(rupiah(old) if old else '-')} → {bold(rupiah(amount))}",
    )


def _cutoff_target(text: str):
    clean = cardref.strip_card_refs(text).strip()
    if not clean:
        raise ValueError("day is missing")
    try:
        day = int(clean)
    except ValueError:
        raise ValueError(f"invalid day: {clean}")
    if not 1 <= day <= 28:
        raise ValueError("cutoff must be 1–28")
    card = _resolve_named_or_default(text)
    return card, day


def cutoff_reply(text: str):
    try:
        card, day = _cutoff_target(text)
    except ValueError as e:
        return messages.err(str(e))
    sheets.update_card_cutoff(card["card_id"], day)
    name = card.get("card_name") or "card"
    return messages.ok(f"Cutoff {name} updated", f"cutoff day → {day}")
