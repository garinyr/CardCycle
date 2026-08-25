"""api/commands/help.py — /help → the button-first menu."""

from core import menu


def handle(text: str) -> str:
    return menu.menu_text()
