"""api/webhook.py — Vercel serverless entrypoint (BaseHTTPRequestHandler).

The Vercel Python runtime detects a class named `handler`.
"""

import json
from http.server import BaseHTTPRequestHandler

from api import auth, config
from api.commands import cards, expense, help as help_cmd, running, statement, summary
from api.telegram import answer_callback, edit_telegram, send_telegram
from core import menu, messages, pending as pending_state, prompts, sheets
from core.formatter import parse_month_arg, today_wib
from core.logger import get_logger, log_event
from core.parser import parse_amount, parse_date

log = get_logger("cc")

# Startup marker — appears in Vercel runtime logs on every cold start / redeploy.
log_event(log, "app_start", version=config.APP_VERSION, ok=True)

SLASH_REDIRECT = "Slash commands are no longer used — use the buttons below 👇"
FALLBACK = "I don't understand — please pick a button below"


def _retry_markup(hint: str) -> dict:
    """ForceReply markup. The hint lives in the input placeholder, never in the
    message text — so the next `reply_to_message.text` still exact-matches the
    prompt constant (prompts.py)."""
    return {"force_reply": True, "input_field_placeholder": hint}


def _force_reply_markup() -> dict:
    return _retry_markup("Reply to this message")


# --- expense card picker (MVP2 Option D) ---

def _sticky_expense_card() -> dict | None:
    raw = (sheets.get_config() or {}).get(config.CONFIG_EXPENSE_CARD_ID, "")
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    for c in sheets.get_cards():
        if c["card_id"] == value and c.get("is_active"):
            return c
    return None


def _expense_entry():
    """Tap 💳 Expense: >1 active card → chip picker first; else straight to the
    prompt (v1.0.0 behavior)."""
    default = sheets.get_default_card()
    if default is None:
        return messages.err("No card set up yet. Prepare the Cards sheet first."), menu.reply_keyboard()
    active = [c for c in sheets.get_cards() if c.get("is_active")]
    if len(active) <= 1:
        return prompts.PROMPT_EXPENSE_INPUT, _force_reply_markup()
    sticky = _sticky_expense_card()
    text = "💳 Expense — record to which card?"
    return text, menu.expense_choice_keyboard(default, sticky)


def _send_expense_prompt(chat_id, card: dict) -> None:
    """After a chip pick: remember the card and send the prompt + ForceReply.
    The chosen card is visible in the placeholder so the user never mis-posts."""
    sheets.upsert_config(config.CONFIG_EXPENSE_CARD_ID, str(card["card_id"]))
    name = card.get("card_name") or "card"
    send_telegram(
        chat_id,
        prompts.PROMPT_EXPENSE_INPUT,
        reply_markup=_retry_markup(f"Recording to {name} — type amount + description"),
    )


def _expense_callback(action: str, chat_id, message_id) -> None:
    pending_state.clear_pending()
    if action == "other":
        default = sheets.get_default_card()
        cards = sheets.get_cards()
        edit_telegram(chat_id, message_id, "💳 Expense — pick a card:",
                      reply_markup=menu.expense_pick_keyboard(cards, default))
        return
    if action.startswith("pick:"):
        try:
            card_id = int(action.split(":", 1)[1])
        except (IndexError, ValueError):
            return
        card = sheets.get_card(card_id)
        if card is None or not card.get("is_active"):
            return
        _send_expense_prompt(chat_id, card)
        return



def _cutoff() -> int:
    card = sheets.get_default_card()
    return (card or {}).get("cutoff_day") or 13


def _safe(fn, arg) -> tuple[str, dict]:
    """Run a handler → (text, markup). Normalize str → (str, reply keyboard);
    pass tuples through. On exception reply with a warning + the menu."""
    try:
        out = fn(arg)
        return out if isinstance(out, tuple) else (out, menu.reply_keyboard())
    except Exception:
        log.exception("handler_error")
        return messages.warn("Something went wrong. Please try again later."), menu.reply_keyboard()


# --- feature views (text + inline markup, card-aware) ---

from core.cycle import cycle_label_for, prev_cycle_label  # noqa: E402
from core.formatter import render_statement  # noqa: E402


def _default_label(card, prefix: str) -> str:
    cutoff = card.get("cutoff_day") or 13
    running = cycle_label_for(today_wib(), cutoff)
    return prev_cycle_label(running) if prefix == "stmt" else running


def _render_card(card, prefix: str, label: str, detail: bool = False) -> str:
    transactions = sheets.read_transactions()
    title = "Running" if prefix == "run" else "Statement"
    return render_statement(card, transactions, label, detail=detail, title=title)


def _view_markup(card, prefix: str, detail: bool = False, viewing: str | None = None) -> dict:
    cutoff = card.get("cutoff_day") or 13
    default = sheets.get_default_card()
    show_other = default is not None and card["card_id"] == default["card_id"]
    markup = menu.month_keyboard(
        today_wib(), cutoff, prefix=prefix, card_id=card["card_id"],
        detail=detail, current=viewing, count=3, months=(prefix == "stmt"),
        show_other=show_other,
    )
    active = [c for c in sheets.get_cards() if c.get("is_active")]
    if len(active) > 1:
        markup["inline_keyboard"].append(
            [{"text": "🗂 All cards", "callback_data": f"{prefix}:all:{card['card_id']}"}]
        )
    return markup


def _view_for(card, prefix: str, month_arg: str = "", detail: bool = False):
    label = parse_month_arg(month_arg.strip(), today_wib()) if month_arg.strip() else _default_label(card, prefix)
    text = _render_card(card, prefix, label, detail=detail)
    return text, _view_markup(card, prefix, detail=detail, viewing=label)


def _default_card_view(prefix: str):
    card = sheets.get_default_card()
    if card is None:
        return messages.no_card(), menu.reply_keyboard()
    return _view_for(card, prefix)


# --- ForceReply prompt reply handlers ---

def _expense_input_reply(text: str):
    # Partial failures are reported inside expense.handle (n saved / n failed);
    # no retry loop for free-text input.
    return expense.handle(text), menu.reply_keyboard()


def _statement_month_reply(text: str):
    clean = " ".join(t for t in text.split() if not t.startswith("@"))
    if parse_month_arg(clean.strip(), today_wib()) is None:
        return prompts.PROMPT_STATEMENT_MONTH, _retry_markup("Unknown format, try: mar25")
    return statement.handle(text), menu.reply_keyboard()


def _running_month_reply(text: str):
    clean = " ".join(t for t in text.split() if not t.startswith("@"))
    if parse_month_arg(clean.strip(), today_wib()) is None:
        return prompts.PROMPT_RUNNING_MONTH, _retry_markup("Unknown format, try: mar25")
    return running.handle(text), menu.reply_keyboard()


def _cards_reply(fn):
    """Reply handler for a Limit/Cutoff prompt (active or stale).

    With an active pending context the value is applied (pending cleared on
    success). Without one the prompt is stale — guide to tap the action again
    instead of letting the text fall through to the expense shortcut."""
    def reply(text: str):
        if pending_state.pending() is None:
            return messages.err("That prompt is no longer active — tap the card action again."), menu.reply_keyboard()
        out = fn(text)
        if not out.startswith("❌"):
            pending_state.clear_pending()
        return out, menu.reply_keyboard()
    return reply


def _cards_add_reply(text: str):
    """Reply path for the Add prompt: preview + confirm buttons; stale prompt
    (no pending) is rejected instead of falling through."""
    if pending_state.pending() is None:
        return messages.err("That prompt is no longer active — tap the card action again."), menu.reply_keyboard()
    preview, _ = cards.start_add(text)
    if preview.startswith("❌"):
        return preview, menu.reply_keyboard()
    return preview, menu.add_confirm_keyboard()


PROMPT_HANDLERS = {
    prompts.PROMPT_EXPENSE_INPUT: _expense_input_reply,
    prompts.PROMPT_STATEMENT_MONTH: _statement_month_reply,
    prompts.PROMPT_RUNNING_MONTH: _running_month_reply,
    prompts.PROMPT_CARDS_ADD: _cards_add_reply,
    prompts.PROMPT_CARDS_LIMIT: _cards_reply(cards.limit_reply),
    prompts.PROMPT_CARDS_CUTOFF: _cards_reply(cards.cutoff_reply),
}


# --- menu tap flows ---

def _menu_flow(cmd: str):
    """Button tap → the feature's entry flow (ForceReply prompt or a view)."""
    if cmd == "expense":
        return _expense_entry()
    if cmd == "statement":
        return _default_card_view("stmt")
    if cmd == "running":
        return _default_card_view("run")
    if cmd == "cards":
        default = sheets.get_default_card()
        return cards.view(), menu.cards_pick_keyboard(sheets.get_cards(), default)
    if cmd == "summary":
        return summary.handle(), menu.reply_keyboard()
    return help_cmd.handle(""), menu.reply_keyboard()  # help


# --- inline callback handling ---

def _callback_dispatch(prefix: str, action: str, token: str, chat_id, message_id):
    """Render a feature for an inline callback and edit the message in place."""
    if prefix == "exp":
        _expense_callback(action, chat_id, message_id)
        return

    if prefix == "cards":
        if action == "add":
            pending_state.set_pending("add")
            send_telegram(chat_id, prompts.PROMPT_CARDS_ADD, reply_markup=menu.pending_cancel_keyboard())
            return
        if action == "list":
            pending_state.clear_pending()
            default = sheets.get_default_card()
            edit_telegram(chat_id, message_id, cards.view(),
                          reply_markup=menu.cards_pick_keyboard(sheets.get_cards(), default))
            return
        if action == "sel":
            pending_state.clear_pending()
            try:
                card_id = int(token)
            except (TypeError, ValueError):
                return
            card = sheets.get_card(card_id)
            if card is None or not card.get("is_active"):
                return
            edit_telegram(chat_id, message_id, cards.describe(card_id),
                          reply_markup=menu.cards_actions_keyboard(card, sheets.get_default_card()))
            return
        if action == "main":
            pending_state.clear_pending()
            try:
                card_id = int(token)
            except (TypeError, ValueError):
                return
            reply = cards.set_main(card_id)
            default = sheets.get_default_card()
            edit_telegram(chat_id, message_id, reply,
                          reply_markup=menu.cards_pick_keyboard(sheets.get_cards(), default))
            return
        if action == "cancel":
            pending_state.clear_pending()
            edit_telegram(chat_id, message_id, "✖️ Cancelled.", reply_markup={"inline_keyboard": []})
            return
        if action in ("addyes", "addno"):
            reply = cards.confirm_add(action == "addyes")
            edit_telegram(chat_id, message_id, reply, reply_markup={"inline_keyboard": []})
            return
        if action in ("lmt", "cut"):
            try:
                card_id = int(token)
            except (TypeError, ValueError):
                return
            card = sheets.get_card(card_id)
            if card is None or not card.get("is_active"):
                return
            pending_state.set_pending(action, card_id)
            prompt = prompts.PROMPT_CARDS_LIMIT if action == "lmt" else prompts.PROMPT_CARDS_CUTOFF
            send_telegram(chat_id, prompt, reply_markup=menu.pending_cancel_keyboard())
        return

    # note: stmt/run callbacks are routed via _month_callback in _handle_callback.


def _month_callback(parts: list[str], chat_id, message_id) -> None:
    """stmt/run inline callbacks (MVP2 card-aware tokens)."""
    pending_state.clear_pending()
    prefix = parts[0]
    kind = parts[1] if len(parts) > 1 else ""

    if kind == "all" and len(parts) >= 3:
        viewing = int(parts[2])
        default = sheets.get_default_card()
        cards = [c for c in sheets.get_cards() if c.get("is_active")]
        rows = []
        for c in cards:
            label = f"💳 {c['card_name']}"
            if default is not None and c["card_id"] == default["card_id"]:
                label += " ⭐"
            if c["card_id"] == viewing:
                label += " (viewing)"
            rows.append([{"text": label, "callback_data": f"{prefix}:view:{c['card_id']}"}])
        rows.append([{"text": "↩️ Back", "callback_data": f"{prefix}:back:{viewing}"}])
        title = "Statement" if prefix == "stmt" else "Running"
        edit_telegram(chat_id, message_id, f"{title} — pick a card:", reply_markup={"inline_keyboard": rows})
        return

    if kind in ("view", "back") and len(parts) >= 3:
        try:
            card = sheets.get_card(int(parts[2]))
        except (TypeError, ValueError):
            return
        if card is None:
            return
        text, markup = _view_for(card, prefix)
        edit_telegram(chat_id, message_id, text, reply_markup=markup)
        return

    if kind == "other" and len(parts) >= 3:
        # Other-month typing targets the default card only (stateless rule).
        default = sheets.get_default_card()
        try:
            card = sheets.get_card(int(parts[2]))
        except (TypeError, ValueError):
            return
        if card is None or default is None or card["card_id"] != default["card_id"]:
            return
        prompt = prompts.PROMPT_STATEMENT_MONTH if prefix == "stmt" else prompts.PROMPT_RUNNING_MONTH
        send_telegram(chat_id, prompt, reply_markup=_force_reply_markup())
        return

    # month tap / detail toggle: [prefix, card_id, month, (detail_*)].
    try:
        cid = int(parts[1])
    except (TypeError, ValueError, IndexError):
        return
    card = sheets.get_card(cid)
    if card is None or len(parts) < 3:
        return
    label = parse_month_arg(parts[2], today_wib())
    if label is None:
        return
    detail = len(parts) >= 4 and parts[3] == "detail_on"
    text = _render_card(card, prefix, label, detail=detail)
    edit_telegram(chat_id, message_id, text, reply_markup=_view_markup(card, prefix, detail=detail, viewing=label))


def _handle_callback(callback: dict):
    cb_id = callback.get("id")
    data_s = callback.get("data") or ""
    msg = callback.get("message") or {}
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")

    if cb_id:
        answer_callback(cb_id)

    if not chat_id or not message_id or not data_s:
        return

    parts = data_s.split(":")
    prefix = parts[0] if parts else ""
    if prefix in ("stmt", "run") and len(parts) >= 2:
        _month_callback(parts, chat_id, message_id)
        return
    action = parts[1] if len(parts) > 1 else ""
    token = parts[2] if len(parts) > 2 else ""
    _callback_dispatch(prefix, action, token, chat_id, message_id)


# --- text routing ---

def _extract_command(text: str) -> str | None:
    if not text.startswith("/"):
        return None
    return text[1:].split(None, 1)[0].lower().split("@")[0]


def _looks_like_expense(text: str) -> bool:
    """Optional shortcut: a message that starts with a date or an amount is
    treated as an expense entry, even without tapping the button first."""
    first = text.split(None, 1)[0] if text else ""
    if not first:
        return False
    try:
        if parse_date(first, today_wib()) is not None:
            return True
    except ValueError:
        pass
    try:
        parse_amount(first)
        return True
    except ValueError:
        return False


def _route(message: dict) -> tuple[str, dict]:
    """Route a chat message → (reply_text, reply_markup). Routing priority:

    1. reply to a ForceReply prompt (exact match on reply_to_message.text)
    2. menu label tap → feature entry flow (clears any pending card input)
    3. slash → /start, /help show the menu; other slash redirects (pending cleared)
    4. pending card input → consume the free text for the active action
    5. (optional) direct expense entry
    6. fallback
    """
    text = (message.get("text") or "").strip()

    # 1. Reply to a ForceReply prompt.
    reply_to = message.get("reply_to_message") or {}
    prompt_fn = PROMPT_HANDLERS.get((reply_to.get("text") or "").strip())
    if prompt_fn:
        return _safe(prompt_fn, text)

    # 2. Menu label tap → feature entry flow. The user moved on: clear pending.
    cmd = menu.cmd_for_label(text)
    if cmd:
        pending_state.clear_pending()
        return _safe(_menu_flow, cmd)

    # 3. Slash → clear pending, then menu (/start,/help) or redirect.
    if text.startswith("/"):
        pending_state.clear_pending()
        if _extract_command(text) in ("start", "help"):
            return help_cmd.handle(""), menu.reply_keyboard()
        return SLASH_REDIRECT, menu.reply_keyboard()

    # 4. Pending card input → consume free text.
    p = pending_state.pending()
    if p:
        action = p[0]
        if action == "add":
            reply, _ = cards.start_add(text)
            if reply.startswith("❌"):
                return reply, menu.pending_cancel_keyboard()  # keep pending, allow cancel
            return reply, menu.add_confirm_keyboard()
        fn = {"limit": cards.limit_reply, "cutoff": cards.cutoff_reply}.get(action)
        if fn:
            reply = fn(text)
            if not reply.startswith("❌"):
                pending_state.clear_pending()
            return reply, menu.reply_keyboard()

    # 5. Direct expense entry (date/amount first).
    if _looks_like_expense(text):
        return _safe(expense.handle, text)

    # 6. Fallback.
    return FALLBACK, menu.reply_keyboard()


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self._respond(200, "CardCycle webhook is running.")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        chat_id = None
        try:
            # validate secret token → log the result only, never the token
            if config.WEBHOOK_SECRET:
                provided = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
                valid = provided == config.WEBHOOK_SECRET
                log_event(log, "auth_secret", valid=valid)
                if not valid:
                    self._respond(401, "Unauthorized")
                    return

            data = json.loads(body)

            callback = data.get("callback_query")
            if callback:
                if auth.check_authorized(callback):
                    try:
                        _handle_callback(callback)
                    except Exception:
                        log.exception("callback_error")
                self._respond(200, "OK")
                return

            message = data.get("message") or data.get("edited_message")

            if not message:
                log_event(log, "webhook", message=False)
                self._respond(200, "OK")
                return

            chat_id = message.get("chat", {}).get("id")

            # validate user_id → log authorized boolean only, not the id
            authorized = auth.check_authorized(message)
            log_event(log, "auth_user", authorized=authorized)
            if not authorized:
                if chat_id:
                    send_telegram(chat_id, messages.warn("Sorry, this bot is for personal use only."))
                self._respond(200, "OK")
                return

            text = (message.get("text") or "").strip()
            cmd = _extract_command(text)
            log_event(log, "command", command=cmd or "none")

            if text and chat_id:
                reply, markup = _route(message)
                send_telegram(chat_id, reply, reply_markup=markup)

        except Exception:
            log.exception("Unhandled error in do_POST")
            if chat_id:
                try:
                    send_telegram(chat_id, messages.warn("Something went wrong. Please try again later."))
                except Exception:
                    pass

        self._respond(200, "OK")

    def _respond(self, code: int, body: str) -> None:
        encoded = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        pass  # suppress default access logs (so our own logs stand out)
