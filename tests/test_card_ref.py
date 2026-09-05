"""tests/test_card_ref.py — @name card-reference resolver (MVP2 groundwork)."""

from core import cardref

CARDS = [
    {"card_id": 1, "card_name": "BNI Mastercard", "is_active": True},
    {"card_id": 2, "card_name": "BNI Xtra", "is_active": True},
    {"card_id": 3, "card_name": "Tokopedia Card", "is_active": True},
    {"card_id": 4, "card_name": "JAGO", "is_active": False},
]


def _ids(cards: list[dict]) -> list[int]:
    return sorted(c["card_id"] for c in cards)


# --- extract_at_refs ---

def test_extract_single_ref():
    assert cardref.extract_at_refs("@tokped 50000 kopi") == ["tokped"]


def test_extract_no_ref():
    assert cardref.extract_at_refs("150000 kopi") == []


def test_extract_multiple_refs():
    assert cardref.extract_at_refs("@a @b x") == ["a", "b"]


def test_extract_empty_and_none():
    assert cardref.extract_at_refs("") == []
    assert cardref.extract_at_refs(None) == []


def test_extract_case_insensitive():
    assert cardref.extract_at_refs("@TokPed 50000") == ["tokped"]


# --- find_candidates / resolve_ref ---

def test_exact_name_wins_over_prefix():
    # "bni" would prefix-match both; the full name is exact.
    card, _ = cardref.resolve_ref("bni mastercard", CARDS)
    assert card["card_id"] == 1


def test_prefix_unique():
    card, _ = cardref.resolve_ref("tok", CARDS)
    assert card["card_id"] == 3


def test_prefix_ambiguous_returns_candidates():
    card, matches = cardref.resolve_ref("bni", CARDS)
    assert card is None
    assert _ids(matches) == [1, 2]


def test_partial_unique():
    card, _ = cardref.resolve_ref("tokopedia", CARDS)
    assert card["card_id"] == 3


def test_unknown_ref_no_match():
    card, matches = cardref.resolve_ref("nonexistent", CARDS)
    assert card is None
    assert matches == []


def test_inactive_card_never_matches():
    card, matches = cardref.resolve_ref("jago", CARDS)
    assert card is None
    assert matches == []


def test_empty_ref_no_match():
    card, matches = cardref.resolve_ref("", CARDS)
    assert card is None
    assert matches == []


def test_resolve_is_case_and_whitespace_tolerant():
    card, _ = cardref.resolve_ref("  TOKO  ", CARDS)
    assert card["card_id"] == 3


def test_empty_card_list():
    card, matches = cardref.resolve_ref("bni", [])
    assert card is None
    assert matches == []
