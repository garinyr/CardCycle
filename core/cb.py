"""core/cb.py — generic inline-callback identifiers (single source of truth).

Telegram inline buttons carry `callback_data` strings (`prefix:token[:data]`).
Keyboard builders (core/menu.py) create them here; the webhook parses them
here. Each feature registers its prefix + its token pairs in `ACTIONS`, so
a token can never drift between the two consumers (bug class: 'cut' vs
'cutoff').

Convention: `ACTIONS[prefix]` maps a canonical action name → transport token.
Identity tokens (token == canonical name) still get listed so *every* token a
feature uses lives in this one file.

Token grammar (full):

| callback_data | meaning |
|---|---|
| `cards:add` / `cards:sel:<id>` / `cards:main:<id>` / `cards:list` / `cards:cancel` / `cards:addyes` / `cards:addno` | Cards flow (identity tokens) |
| `cards:limit:<id>` / `cards:cutoff:<id>` | Cards flow — canonical `limit`/`cutoff` (data = card id) |
| `exp:pick:<id>` / `exp:other` | Expense chip picker |
| `stmt:<card_id>:<month>` | statement month tap (data-led: card + month) |
| `stmt:detail_on / detail_off:<card_id>:<month>` | statement detail toggle (action-led) |
| `stmt:all:<viewing_id>` / `stmt:view:<id>` / `stmt:back:<id>` / `stmt:other:<id>` | statement card nav |
| same set with `run:` prefix | running views |
"""

PREFIX_CARDS = "cards"
PREFIX_EXP = "exp"
PREFIX_STMT = "stmt"
PREFIX_RUN = "run"

# Canonical card-action names (single source — registry keys reference them).
CARDS_ACTION_ADD = "add"
CARDS_ACTION_SEL = "sel"
CARDS_ACTION_MAIN = "main"
CARDS_ACTION_LIST = "list"
CARDS_ACTION_CANCEL = "cancel"
CARDS_ACTION_ADDYES = "addyes"
CARDS_ACTION_ADDNO = "addno"
CARDS_ACTION_LIMIT = "limit"
CARDS_ACTION_CUTOFF = "cutoff"

# Canonical expense-flow action names.
EXP_ACTION_PICK = "pick"
EXP_ACTION_OTHER = "other"

# canonical action name → callback token, per feature prefix.
ACTIONS: dict[str, dict[str, str]] = {
    PREFIX_CARDS: {
        CARDS_ACTION_ADD: "add",
        CARDS_ACTION_SEL: "sel",
        CARDS_ACTION_MAIN: "main",
        CARDS_ACTION_LIST: "list",
        CARDS_ACTION_CANCEL: "cancel",
        CARDS_ACTION_ADDYES: "addyes",
        CARDS_ACTION_ADDNO: "addno",
        CARDS_ACTION_LIMIT: "limit",
        CARDS_ACTION_CUTOFF: "cutoff",
    },
    PREFIX_EXP: {
        EXP_ACTION_PICK: "pick",
        EXP_ACTION_OTHER: "other",
    },
    PREFIX_STMT: {
        "all": "all",
        "view": "view",
        "back": "back",
        "other": "other",
        "detail_on": "detail_on",
        "detail_off": "detail_off",
    },
    PREFIX_RUN: {
        "all": "all",
        "view": "view",
        "back": "back",
        "other": "other",
        "detail_on": "detail_on",
        "detail_off": "detail_off",
    },
}

_TOKEN_BY_ACTION = {prefix: {v: k for k, v in m.items()} for prefix, m in ACTIONS.items()}


def token_of(prefix: str, action: str) -> str:
    """Transport token for a canonical action name (menu builders)."""
    try:
        return ACTIONS[prefix][action]
    except KeyError:
        raise KeyError(f"unknown action {action!r} for prefix {prefix!r}") from None


def action_of(prefix: str, token: str) -> str:
    """Canonical action name for a transport token (webhook parsing)."""
    try:
        return _TOKEN_BY_ACTION[prefix][token]
    except KeyError:
        raise KeyError(f"unknown token {token!r} for prefix {prefix!r}") from None


def build(prefix: str, action: str, *data) -> str:
    """Build `prefix:token[:data…]` from a canonical action name."""
    parts = [prefix, token_of(prefix, action)]
    parts.extend(str(d) for d in data)
    return ":".join(parts)


def parse(data: str) -> tuple[str, str, list[str]]:
    """Split `callback_data` → (prefix, token, data-parts)."""
    parts = data.split(":")
    prefix = parts[0] if parts else ""
    token = parts[1] if len(parts) > 1 else ""
    return prefix, token, parts[2:]
