"""core/logger.py — centralized structured logging (WIB), PII-safe.

`logging.basicConfig` at root, then modules use `logging.getLogger(name)` with
propagate (default) to root. Do NOT attach a per-logger handler + `propagate=False`
— on Vercel only logs that propagate to the root logger get captured.

Do NOT log message content (text/description) because it may contain PII.
"""

import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Jakarta")

_FMT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


class _WIBFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, TZ)
        return dt.isoformat(timespec="seconds")


def _configure_root() -> None:
    # basicConfig is a no-op if root already has a handler; apply WIB formatter to all root handlers.
    logging.basicConfig(level=logging.INFO, format=_FMT, stream=sys.stdout)
    for h in logging.getLogger().handlers:
        h.setFormatter(_WIBFormatter(_FMT))


_configure_root()


def get_logger(name: str) -> logging.Logger:
    """Return a logger with no own handler — propagate to root."""
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **fields) -> None:
    """Emit one structured line: `event=... key=value ...` (skip None)."""
    parts = [f"event={event}"]
    for k, v in fields.items():
        if v is None:
            continue
        parts.append(f"{k}={v}")
    logger.info(" ".join(parts))
