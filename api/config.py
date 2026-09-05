"""api/config.py — environment variables & sheet constants."""

import os

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "")
SHEET_CARDS = "Cards"
SHEET_CONFIG = "Config"
SHEET_TRANSACTIONS = "Transactions"

# Config keys
CONFIG_NEXT_ID = "next_id"
CONFIG_NEXT_CARD_ID = "next_card_id"
CONFIG_DEFAULT_CARD_ID = "default_card_id"
CONFIG_EXPENSE_CARD_ID = "expense_card_id"
CONFIG_CARDS_EDIT_CARD_ID = "cards.edit_card_id"

AUTHORIZED_USER_ID = int(os.environ.get("TELEGRAM_USER_ID") or "0")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

# Bump to mark a deploy in the logs; can be overridden via APP_VERSION env.
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")

# Sheet layout (column order).
CARDS_HEADERS = [
    "card_id", "card_name", "bank", "card_limit", "cutoff_day",
    "due_day", "is_active", "created_at", "updated_at",
]
CONFIG_HEADERS = ["key", "value", "description", "updated_at"]
TRANSACTIONS_HEADERS = [
    "id", "card_id", "date", "amount", "description",
    "category", "deleted", "input_at",
]
