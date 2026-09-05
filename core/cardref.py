"""core/cardref.py — resolve '@name' card references (MVP2 groundwork).

Pure functions over card-row dicts (the shape produced by core/sheets.py
`_coerce_card`): `{card_id, card_name, bank, card_limit, cutoff_day, due_day,
is_active, ...}`. No sheets/network access here — callers pass the card list.

Rules (see docs/card-cycle/migration/mvp1-to-mvp2-plan.md §P1):
- A reference is an `@token` (no spaces) anywhere in free text.
- Resolution matches **active** cards only, in this order:
  1. exact (case-insensitive on the whole name),
  2. prefix (name starts with the token),
  3. partial (token is a substring of the name).
- Unambiguous single match -> that card. Several matches -> `(None, matches)`
  so the caller can ask the user to be more specific. No match -> `(None, [])`.
- Inactive cards are never returned for an `@name`; the default-card path
  (no `@`) is separate and keeps its own rules (D4).
"""

import re

_AT_TOKEN_RE = re.compile(r"@([A-Za-z0-9_.\-]+)")


def extract_at_refs(text: str) -> list[str]:
    """Return the raw `@token` references in `text` (without the '@', lowercased)."""
    if not text:
        return []
    return [m.group(1).lower() for m in _AT_TOKEN_RE.finditer(text)]


def _norm(name) -> str:
    return str(name or "").strip().lower()


def find_candidates(ref: str, cards: list[dict]) -> list[dict]:
    """Active cards matching `ref` (exact -> prefix -> partial order wins)."""
    key = ref.strip().lower()
    if not key:
        return []
    active = [c for c in cards if c.get("is_active")]
    exact = [c for c in active if _norm(c.get("card_name")) == key]
    if exact:
        return exact
    prefix = [c for c in active if _norm(c.get("card_name")).startswith(key)]
    if prefix:
        return prefix
    return [c for c in active if key in _norm(c.get("card_name"))]


def resolve_ref(ref: str, cards: list[dict]) -> tuple[dict | None, list[dict]]:
    """Resolve one `@name` ref -> (card, candidates).

    Returns `(card, [])` on a unique active match, `(None, matches)` when the
    ref is ambiguous, and `(None, [])` when nothing matches.
    """
    matches = find_candidates(ref, cards)
    if len(matches) == 1:
        return matches[0], []
    return None, matches


def strip_card_refs(text: str) -> str:
    """Return `text` with every `@token` removed, preserving line structure.

    Rebuilds each line without `@`-tokens so multi-line batches keep their
    rows (never collapse newlines).
    """
    if not text:
        return ""
    lines = []
    for line in text.splitlines():
        lines.append(" ".join(tok for tok in line.split() if not tok.startswith("@")))
    return "\n".join(lines)


def command_card(text: str, cards: list[dict] | None = None, default_card: dict | None = None) -> tuple[dict | None, str | None]:
    """Resolve the card a command message targets.

    An `@name` (active-only) wins over the default card; with no `@` the
    `default_card` is used (may be None). `cards` is only consulted when a ref
    is present — callers may pass None when the text has no `@`. Returns
    `(card, None)` on success or `(None, error_message)` when the target can't
    be resolved (unknown card, ambiguous match, multiple refs, no active card).
    """
    refs = extract_at_refs(text)
    if len(refs) > 1:
        return None, "Multiple @card references — use one per message."
    if refs:
        cards = cards or []
        ref = refs[0]
        card, candidates = resolve_ref(ref, cards)
        if card is not None:
            return card, None
        if candidates:
            names = ", ".join(str(c.get("card_name")) for c in candidates)
            return None, f"Ambiguous @{ref} — matches: {names}. Be more specific."
        active = [c for c in cards if c.get("is_active")]
        if active:
            names = ", ".join(str(c.get("card_name")) for c in active)
            return None, f"Unknown card: @{ref}. Available: {names}."
        return None, "No active cards yet."
    return default_card, None
