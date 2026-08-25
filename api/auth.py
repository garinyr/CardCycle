"""api/auth.py — whitelist user."""

from api import config


def check_authorized(message: dict) -> bool:
    """True if sender's user_id == AUTHORIZED_USER_ID (fail-closed when 0)."""
    user_id = message.get("from", {}).get("id")
    if not config.AUTHORIZED_USER_ID:
        return False
    return user_id == config.AUTHORIZED_USER_ID
