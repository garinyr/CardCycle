"""core/messages.py — standardized response templates (parse_mode HTML).

Consistency across commands:
- Every message starts with a status emoji (✅ success, ❌ error, ⚠️ warning).
- Multi-line blocks use `block` + DIVIDER, not manual `\n`.
- All string arguments are HTML-escaped (user content is safe).
- Sentences start with a capital letter after the emoji.
"""

from core.formatter import DIVIDER, block, bold, esc, mono


def ok(title: str, *body: str) -> str:
    """Success message — ✅ bold title, body below the divider."""
    return block(f"✅ {bold(title)}", DIVIDER, "", *body)


def info(title: str, *body: str) -> str:
    """Info message — 📋 bold title, body below the divider."""
    return block(f"📋 {bold(title)}", DIVIDER, "", *body)


def err(message: str) -> str:
    """Single-line error message — ❌."""
    return f"❌ {esc(message)}"


def warn(message: str) -> str:
    """Single-line warning message — ⚠️."""
    return f"⚠️ {esc(message)}"


def usage(cmd: str, syntax: str, example: str) -> str:
    """Short usage hint — shown when input is empty/invalid."""
    return block(
        f"📖 {bold(f'How to use /{cmd}')}",
        DIVIDER,
        "",
        f"Format : {mono(syntax)}",
        f"Example: {mono(example)}",
    )


def no_card() -> str:
    """Standard message when there is no active card yet."""
    return err("No card set up yet. Prepare the Cards sheet first.")


def unknown_command(cmd: str) -> str:
    """Standard message for an unknown command."""
    return block(err(f"Unknown command: /{cmd}"), "", "💡 Type /help for help")
