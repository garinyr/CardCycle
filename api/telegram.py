"""api/telegram.py — reusable Telegram Bot API client."""

import os

import requests

from core.logger import get_logger, log_event

logger = get_logger("cc")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")


def _api_call(method: str, payload: dict) -> bool:
    """POST to a Bot API method. Return True if the API returned ok:true."""
    if not BOT_TOKEN:
        log_event(logger, "tg_api", method=method, ok=False, reason="BOT_TOKEN_not_set")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
            json=payload,
            timeout=10,
        )
        # Telegram returns HTTP 200 + {"ok": false} for logical errors
        # (chat not found, message too long, unknown message_id).
        try:
            data = r.json()
        except Exception:
            data = {}
        ok = r.status_code == 200 and bool(data.get("ok"))
        log_event(logger, "tg_api", method=method, ok=ok, http=r.status_code,
                  tg_error=data.get("description") if not ok else None)
        return ok
    except Exception:
        log_event(logger, "tg_api", method=method, ok=False, http="exception")
        return False


def send_telegram(chat_id: int, text: str, reply_markup: dict | None = None, force_reply: bool = False) -> bool:
    """Send a message to a Telegram chat. Return True if the API succeeded.

    reply_markup: any keyboard payload (e.g. menu.reply_keyboard()).
    force_reply:  True pins the reply box to this message (ForceReply).
    """
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if force_reply:
        payload["reply_markup"] = {"force_reply": True, "input_field_placeholder": "Reply to this message"}
    elif reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _api_call("sendMessage", payload)




def edit_telegram(chat_id: int, message_id: int, text: str, reply_markup: dict | None = None) -> bool:
    """Edit an existing message in place (used by the inline month picker)."""
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _api_call("editMessageText", payload)


def answer_callback(callback_id: str) -> bool:
    """Acknowledge a callback_query (dismisses the button loading spinner)."""
    return _api_call("answerCallbackQuery", {"callback_query_id": callback_id})
