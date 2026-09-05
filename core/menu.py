"""core/menu.py — reply-keyboard main menu + inline keyboards.

Menu = persistent Telegram ReplyKeyboardMarkup (tap sends the label as text).
Inline keyboards (month picker, detail toggle, limit edit) live under a message
and fire callback_query.
"""

from core.cycle import cycle_label_for, prev_cycle_label
from core.formatter import DIVIDER, block, bold

BTN_EXPENSE = "💳 Expense"
BTN_STATEMENT = "📄 Statement"
BTN_RUNNING = "📊 Running"
BTN_CARDS = "🗂 Cards"
BTN_SUMMARY = "📊 Summary"
BTN_HELP = "ℹ️ Help"

# 3×2 grid, Help last.
MENU = [
    [BTN_EXPENSE, BTN_STATEMENT],
    [BTN_RUNNING, BTN_CARDS],
    [BTN_SUMMARY, BTN_HELP],
]

_LABEL_TO_CMD = {
    BTN_EXPENSE: "expense",
    BTN_STATEMENT: "statement",
    BTN_RUNNING: "running",
    BTN_CARDS: "cards",
    BTN_SUMMARY: "summary",
    BTN_HELP: "help",
}

_MONTH_ABBR = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


def cmd_for_label(text: str | None) -> str | None:
    """Map a tapped button label to its command key, else None."""
    return _LABEL_TO_CMD.get(text.strip()) if isinstance(text, str) else None


def reply_keyboard() -> dict:
    """Telegram ReplyKeyboardMarkup payload — persistent bottom-bar menu."""
    return {
        "keyboard": [[{"text": label} for label in row] for row in MENU],
        "resize_keyboard": True,
        "input_field_placeholder": "Tap a button, or type a command",
    }


def menu_text() -> str:
    """Compact menu/help body — one line per action."""
    return block(
        f"{bold('💳 CardCycle')} — tap a button below",
        DIVIDER,
        "",
        f"{BTN_EXPENSE} — Record spending (needs typing)",
        f"{BTN_STATEMENT} — Latest issued statement + utilization",
        f"{BTN_RUNNING} — Current (running) cycle + utilization",
        f"{BTN_CARDS} — List / manage your cards (limit, cutoff, default)",
        f"{BTN_SUMMARY} — All cards' utilization at a glance",
        f"{BTN_HELP} — This help",
    )


# --- month picker (inline) ---

def _token(label: str) -> str:
    """'YYYY-MM' → 'nov25' (callback token understood by parse_month_arg)."""
    y, m = int(label[:4]), int(label[5:7])
    return f"{_MONTH_ABBR[m].lower()}{y % 100:02d}"


def _month_label(label: str) -> str:
    """'YYYY-MM' → 'Nov 25'."""
    y, m = int(label[:4]), int(label[5:7])
    return f"{_MONTH_ABBR[m]} {y % 100:02d}"


def month_keyboard(today, cutoff_day: int, prefix: str = "stmt", card_id: int = 1, detail: bool = False, current: str | None = None, count: int = 6, months: bool = True, show_other: bool = True) -> dict:
    """Inline keyboard for statement/running.

    prefix: 'stmt' (starts at latest frozen) or 'run' (starts at running cycle).
    card_id: the card this picker belongs to — embedded in every token so a
             callback knows which card to render (MVP2 multi-card).
    current: 'YYYY-MM' month currently displayed — drives the detail-toggle token only.
             The grid itself is always anchored to the latest cycle for the prefix,
             so tapping a month renders it without moving the grid.
    count: number of month buttons (older months typed via "Other month").
    months: False → detail toggle only, no month grid / "Other month" (running uses this).
    show_other: False hides "Other month" (non-default-card views; typed months
                target the default card, so the button is only offered there).
    """
    running = cycle_label_for(today, cutoff_day)
    anchor = prev_cycle_label(running) if prefix == "stmt" else running
    viewed = current or anchor

    rows = []

    if months:
        labels = [anchor]
        for _ in range(count - 1):
            labels.append(prev_cycle_label(labels[-1]))
        month_buttons = [
            {"text": _month_label(l), "callback_data": f"{prefix}:{card_id}:{_token(l)}"}
            for l in labels
        ]
        for i in range(0, len(month_buttons), 3):
            rows.append(month_buttons[i:i + 3])

    cur_token = _token(viewed)
    detail_btn = {
        "text": "🔼 Summary" if detail else "🔍 Details",
        "callback_data": f"{prefix}:{card_id}:{cur_token}:detail_off" if detail else f"{prefix}:{card_id}:{cur_token}:detail_on",
    }
    rows.append([detail_btn])

    if months and show_other:
        other_btn = {"text": "📅 Other month", "callback_data": f"{prefix}:other:{card_id}"}
        rows.append([other_btn])

    return {"inline_keyboard": rows}


# --- expense card picker (MVP2 Option D) ---

def cards_pick_keyboard(cards: list[dict], default_card: dict | None = None) -> dict:
    """Cards view inline rows: one tappable row per card (no duplicated actions).

    Tap a card → its own action menu opens in the same message. Add sits at
    the bottom (a new card has no row yet).
    """
    default_id = default_card["card_id"] if default_card else None
    rows = []
    for c in cards:
        if not c.get("is_active"):
            continue
        label = f"💳 {c['card_name']}"
        if c["card_id"] == default_id:
            label += " ⭐"
        rows.append([{"text": label, "callback_data": f"cards:sel:{c['card_id']}"}])
    rows.append([{"text": "➕ Add card", "callback_data": "cards:add"}])
    return {"inline_keyboard": rows}


def cards_actions_keyboard(card: dict, default_card: dict | None = None) -> dict:
    """Action menu for one selected card (single row of actions + Back)."""
    default_id = default_card["card_id"] if default_card else None
    actions = []
    if card["card_id"] != default_id:
        actions.append({"text": "⭐ Make main", "callback_data": f"cards:main:{card['card_id']}"})
    actions.append({"text": "🎯 Limit", "callback_data": f"cards:lmt:{card['card_id']}"})
    actions.append({"text": "📅 Cutoff", "callback_data": f"cards:cut:{card['card_id']}"})
    return {"inline_keyboard": [actions, [{"text": "↩️ Back", "callback_data": "cards:list"}]]}


def pending_cancel_keyboard() -> dict:
    """Cancel button on a plain pending prompt (reply-free input)."""
    return {"inline_keyboard": [[{"text": "✖️ Cancel", "callback_data": "cards:cancel"}]]}


def add_confirm_keyboard() -> dict:
    """Confirm/deny buttons for a parsed Add draft."""
    return {
        "inline_keyboard": [[
            {"text": "✅ Yes, add it", "callback_data": "cards:addyes"},
            {"text": "✖️ No", "callback_data": "cards:addno"},
        ]]
    }


def expense_choice_keyboard(default_card: dict, sticky_card: dict | None) -> dict:
    """First step of the expense flow when >1 active card: chips to pick where
    the batch will be recorded. The current target (sticky or default) leads;
    ⭐ marks the global default; Other opens the full picker."""
    current = sticky_card if sticky_card is not None else default_card
    buttons = [{"text": f"💳 {current['card_name']}", "callback_data": f"exp:pick:{current['card_id']}"}]
    if sticky_card is not None and sticky_card["card_id"] != default_card["card_id"]:
        buttons.append({"text": f"💳 {default_card['card_name']} ⭐", "callback_data": f"exp:pick:{default_card['card_id']}"})
    buttons.append({"text": "🗂 Other card…", "callback_data": "exp:other"})
    return {"inline_keyboard": [buttons]}


def expense_pick_keyboard(cards: list[dict], default_card: dict | None = None) -> dict:
    """Full picker list for the expense flow (when chips aren't enough).
    One button per active card; ⭐ marks the global default."""
    rows = []
    for c in cards:
        if not c.get("is_active"):
            continue
        marker = " ⭐" if default_card is not None and c["card_id"] == default_card["card_id"] else ""
        rows.append([{"text": f"💳 {c['card_name']}{marker}", "callback_data": f"exp:pick:{c['card_id']}"}])
    return {"inline_keyboard": rows}
