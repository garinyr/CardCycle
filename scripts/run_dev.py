"""
scripts/run_dev.py
------------------
Run a local webhook server for testing the Telegram bot.

Usage:
  1. python scripts/run_dev.py          ← start the server (port 8080)
  2. ngrok http 8080                    ← in another terminal, expose to the internet
  3. Register the ngrok URL with Telegram ← see instructions in the output
"""

import os
import sys
from http.server import HTTPServer
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env (BOT_TOKEN, SPREADSHEET_ID, TELEGRAM_USER_ID, WEBHOOK_SECRET)
load_dotenv(BASE_DIR / ".env")

# Set GOOGLE_CREDENTIALS_JSON from the local credentials.json (dev only)
if not os.environ.get("GOOGLE_CREDENTIALS_JSON"):
    creds_path = BASE_DIR / "config" / "credentials.json"
    if creds_path.exists():
        os.environ["GOOGLE_CREDENTIALS_JSON"] = creds_path.read_text(encoding="utf-8")
        print(f"✅ Credentials: {creds_path}")
    else:
        print(f"⚠️  credentials.json not found at {creds_path}")
        sys.exit(1)

if not os.environ.get("BOT_TOKEN"):
    print("⚠️  BOT_TOKEN is not set.")
    print("   Add it to .env: BOT_TOKEN=xxxx:yyyy")
    sys.exit(1)

sys.path.insert(0, str(BASE_DIR))
from api.webhook import handler  # noqa: E402

PORT = int(os.environ.get("PORT", 8080))
server = HTTPServer(("0.0.0.0", PORT), handler)

print(f"Server running on http://localhost:{PORT}")
print(f"Ngrok:  ngrok http {PORT}")

try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\n🛑 Server stopped.")
