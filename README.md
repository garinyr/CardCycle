# CardCycle (cc)

A Telegram bot for recording **credit card spending** to Google Sheets + tracking utilization per billing cycle.

- Personal use: 1 user. One card or many — the schema is multi-card ready
  (`Cards` table): adding a card = adding a row, no code/schema migration.
- Backend: **Google Sheets** (gspread), deployed on **Vercel** serverless (mode **webhook**, not polling).
- Timezone: `Asia/Jakarta` (WIB). Messages use `parse_mode="HTML"`, user input is auto-escaped.

## Usage — tap the buttons (no slash commands)

Everything is **button-first**. A persistent reply-keyboard menu sits at the bottom of the chat and is re-attached on every reply:

| Button | Action |
|---|---|
| 💳 Expense | Record spending (shows format — needs typing) |
| 📄 Statement | Latest issued statement + utilization |
| 📊 Running | Current (running) cycle + utilization |
| 🗂 Cards | List / manage cards (default, limit, cutoff) |
| 📊 Summary | All cards' running-cycle utilization at a glance |
| ℹ️ Help | Menu + format help |
| ℹ️ Help | Menu + format help |

Free-text input is still typed (via ForceReply) for the actions that need it:
**Expense** (amount + description), **adding a card**, and a card's **Limit**
and **Cutoff** values (the card is chosen by button first).

## Documentation

| Topic | File |
|---|---|
| Install, Google Sheets, env, Vercel deploy | [`docs/SETUP.md`](docs/SETUP.md) |
| Button-first usage + examples + format notes | [`docs/USAGE.md`](docs/USAGE.md) |

## Quickstart

```bash
# 1. setup: service account → 3 sheets → env → deploy Vercel  → docs/SETUP.md
# 2. register the webhook
curl "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://<PROJECT>.vercel.app/api/webhook&secret_token=<WEBHOOK_SECRET>"

# 3. send any message in Telegram → the button menu appears
```

## Project Structure

```
card-cycle/
├── requirements.txt
├── vercel.json            ← Vercel deployment config
├── api/                   ← Telegram webhook (Vercel serverless)
│   ├── webhook.py         ← Vercel entrypoint (BaseHTTPRequestHandler)
│   ├── config.py          ← env vars, sheet constants, column headers
│   ├── auth.py            ← whitelist TELEGRAM_USER_ID
│   ├── telegram.py        ← sendMessage client (parse_mode=HTML)
│   └── commands/          ← feature handlers (button flows)
│       ├── help.py        ← menu/help text
│       ├── expense.py     ← expense (single + batch)
│       ├── statement.py   ← statement (frozen cycle + detail)
│       ├── running.py     ← running (current cycle)
│       ├── cards.py       ← cards list + manage (default/limit/cutoff)
│       └── summary.py     ← all-cards utilization glance
├── core/                  ← pure logic + data access
│   ├── cycle.py           ← cutoff logic, cycle_label on-read
│   ├── parser.py          ← parse expense (date, amount, description, batch)
│   ├── utilization.py     ← % + band status (6 levels)
│   ├── sheets.py          ← gspread client, Cards/Config/Transactions
│   ├── formatter.py       ← WIB clock, month names, HTML helpers, render output
│   ├── menu.py            ← reply-keyboard menu (buttons, label→cmd, keyboard payload)
│   └── messages.py        ← standardized response templates (parse_mode HTML)
├── docs/
│   ├── SETUP.md           ← install + deploy
│   └── USAGE.md           ← button-first usage
└── tests/                 ← unit tests (prompts, menu, routing, flows)
```

## Roadmap

Still future: payment tracking (`Payments` sheet), H-3 reminder (Vercel Cron + `due_day` + `ReminderLog`), categories, edit/delete transactions.
