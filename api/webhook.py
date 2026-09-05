"""api/webhook.py — Vercel serverless entrypoint (BaseHTTPRequestHandler).

The Vercel Python runtime detects a class named `handler`.
"""

import json
from http.server import BaseHTTPRequestHandler

from api import auth, config
from api.commands import expense, help as help_cmd, limit, running, statement
from api.telegram import answer_callback, edit_telegram, send_telegram
from core import menu, messages, prompts, sheets
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


# --- feature views (text + inline markup) ---

def _statement_view(month_arg: str = "", detail: bool = False):
    text = statement.handle((month_arg + (" detail" if detail else "")).strip())
    label = parse_month_arg(month_arg.strip(), today_wib()) if month_arg.strip() else None
    markup = menu.month_keyboard(today_wib(), _cutoff(), prefix="stmt", detail=detail, current=label, count=3)
    return text, markup


def _running_view(month_arg: str = "", detail: bool = False):
    text = running.handle((month_arg + (" detail" if detail else "")).strip())
    label = parse_month_arg(month_arg.strip(), today_wib()) if month_arg.strip() else None
    markup = menu.month_keyboard(today_wib(), _cutoff(), prefix="run", detail=detail, current=label, months=False)
    return text, markup


def _limit_view():
    return limit.handle(""), menu.limit_keyboard()


# --- ForceReply prompt reply handlers ---

def _expense_input_reply(text: str):
    # Partial failures are reported inside expense.handle (n saved / n failed);
    # no retry loop for free-text input.
    return expense.handle(text), menu.reply_keyboard()


def _statement_month_reply(text: str):
    if parse_month_arg(text.strip(), today_wib()) is None:
        return prompts.PROMPT_STATEMENT_MONTH, _retry_markup("Unknown format, try: mar25")
    return _statement_view(text.strip())


def _running_month_reply(text: str):
    if parse_month_arg(text.strip(), today_wib()) is None:
        return prompts.PROMPT_RUNNING_MONTH, _retry_markup("Unknown format, try: mar25")
    return _running_view(text.strip())


def _limit_update_reply(text: str):
    try:
        parse_amount(text.strip())
    except ValueError:
        return prompts.PROMPT_LIMIT_UPDATE, _retry_markup("Invalid number, try: 15000000")
    return limit.handle(text), menu.reply_keyboard()


PROMPT_HANDLERS = {
    prompts.PROMPT_EXPENSE_INPUT: _expense_input_reply,
    prompts.PROMPT_STATEMENT_MONTH: _statement_month_reply,
    prompts.PROMPT_RUNNING_MONTH: _running_month_reply,
    prompts.PROMPT_LIMIT_UPDATE: _limit_update_reply,
}


# --- menu tap flows ---

def _menu_flow(cmd: str):
    """Button tap → the feature's entry flow (ForceReply prompt or a view)."""
    if cmd == "expense":
        return _expense_entry()
    if cmd == "statement":
        return _statement_view()
    if cmd == "running":
        return _running_view()
    if cmd == "limit":
        return _limit_view()
    return help_cmd.handle(""), menu.reply_keyboard()  # help


# --- inline callback handling ---

def _callback_dispatch(prefix: str, action: str, token: str, chat_id, message_id):
    """Render a feature for an inline callback and edit the message in place."""
    if prefix == "exp":
        _expense_callback(action, chat_id, message_id)
        return

    if prefix == "limit":
        if action == "edit":
            send_telegram(chat_id, prompts.PROMPT_LIMIT_UPDATE, reply_markup=_force_reply_markup())
        return

    if prefix in ("stmt", "run"):
        if action == "other":
            prompt = prompts.PROMPT_STATEMENT_MONTH if prefix == "stmt" else prompts.PROMPT_RUNNING_MONTH
            send_telegram(chat_id, prompt, reply_markup=_force_reply_markup())
            return

        if action in ("detail_on", "detail_off"):
            detail = action == "detail_on"
            month = token
        else:
            # month tap: action is the token (e.g. "nov25")
            detail = False
            month = action

        view = _statement_view if prefix == "stmt" else _running_view
        text, markup = view(month, detail=detail)
        edit_telegram(chat_id, message_id, text, reply_markup=markup)
        return


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
    2. menu label tap → feature entry flow
    3. (optional) direct expense entry
    4. legacy slash → redirect to the menu
    5. fallback
    """
    text = (message.get("text") or "").strip()

    # 1. Reply to a ForceReply prompt.
    reply_to = message.get("reply_to_message") or {}
    prompt_fn = PROMPT_HANDLERS.get((reply_to.get("text") or "").strip())
    if prompt_fn:
        return _safe(prompt_fn, text)

    # 2. Menu label tap → feature entry flow.
    cmd = menu.cmd_for_label(text)
    if cmd:
        return _safe(_menu_flow, cmd)

    # 3. Direct expense entry (date/amount first).
    if _looks_like_expense(text):
        return _safe(expense.handle, text)

    # 4. Legacy slash → redirect, never silent.
    if text.startswith("/"):
        return SLASH_REDIRECT, menu.reply_keyboard()

    # 5. Fallback.
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
