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
BTN_LIMIT = "🎯 Limit"
BTN_HELP = "ℹ️ Help"

# 2-column grid, Help last.
MENU = [
    [BTN_EXPENSE, BTN_STATEMENT],
    [BTN_RUNNING, BTN_LIMIT],
    [BTN_HELP],
]

_LABEL_TO_CMD = {
    BTN_EXPENSE: "expense",
    BTN_STATEMENT: "statement",
    BTN_RUNNING: "running",
    BTN_LIMIT: "limit",
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
        f"{BTN_LIMIT} — View / update card limit",
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


def month_keyboard(today, cutoff_day: int, prefix: str = "stmt", detail: bool = False, current: str | None = None, count: int = 6, months: bool = True) -> dict:
    """Inline keyboard for statement/running.

    prefix: 'stmt' (starts at latest frozen) or 'run' (starts at running cycle).
    current: 'YYYY-MM' month currently displayed — drives the detail-toggle token only.
             The grid itself is always anchored to the latest cycle for the prefix,
             so tapping a month renders it without moving the grid.
    count: number of month buttons (older months typed via "Other month").
    months: False → detail toggle only, no month grid / "Other month" (running uses this).
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
            {"text": _month_label(l), "callback_data": f"{prefix}:{_token(l)}"}
            for l in labels
        ]
        for i in range(0, len(month_buttons), 3):
            rows.append(month_buttons[i:i + 3])

    cur_token = _token(viewed)
    detail_btn = {
        "text": "🔼 Summary" if detail else "🔍 Details",
        "callback_data": f"{prefix}:{'detail_off' if detail else 'detail_on'}:{cur_token}",
    }
    rows.append([detail_btn])

    if months:
        other_btn = {"text": "📅 Other month", "callback_data": f"{prefix}:other"}
        rows.append([other_btn])

    return {"inline_keyboard": rows}


def limit_keyboard() -> dict:
    """Inline keyboard for the limit view — edit button."""
    return {"inline_keyboard": [[{"text": "✏️ Update Limit", "callback_data": "limit:edit"}]]}
