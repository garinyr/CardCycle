# SETUP — Install & Deploy CardCycle

## 0. Create the Telegram bot (BotFather)

1. In Telegram, open **@BotFather**.
2. `/newbot` → send the bot's **name** (any, e.g. `CardCycle`).
3. Send the **username** — must end in `bot` (e.g. `cardcycle_bot`).
4. BotFather replies with a **token** (`123456789:ABC...`). Copy it → becomes `BOT_TOKEN` in Vercel.

Recommended BotFather settings:

| Command | Setting | Why |
|---|---|---|
| `/setprivacy` | **Disable** | Bot can read all messages in a group (not required for 1-on-1 use) |
| `/setjoingroup` | **Enable** | Allow the bot to be added to groups |
| `/setcommands` | paste list below | Shows a `/` command menu in Telegram |

Command list for `/setcommands`:
```
expense - Record spending
statement - View issued (frozen) statement
running - View the current (running) cycle
limit - View / update card limit
help - List commands & usage
```

## 1. Install dependencies

```bash
cd card-cycle
pip install -r requirements.txt
```

## 2. Google Service Account

`GOOGLE_CREDENTIALS_JSON` = the **full contents** of the service account key file (not a path).

1. Open the [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable the **Google Sheets API**
3. APIs & Services → Credentials → **Create Credentials → Service Account**
4. On the service account → **Keys → Add Key → Create new key** → JSON → download
5. Open the spreadsheet → **Share** → add the `client_email` (from the JSON) → role **Editor**

## 3. Create the spreadsheet (3 sheets)

Create a blank spreadsheet and add 3 sheets: `Cards`, `Config`, `Transactions`.
Row 1 = header (columns in this order):

**`Cards`** — one row per card; add more cards by appending rows (no schema
change). First new card gets `card_id = 2` (from `Config.next_card_id`):
```
card_id | card_name | bank | card_limit | cutoff_day | due_day | is_active | created_at | updated_at
1       | BNI       | BNI  | 15000000   | 13         | 15      | TRUE      | 2026-08-23 | 2026-08-23
```

**`Config`** — app-level key-value:
```
key              | value | description
next_card_id     | 2     | card id counter (monotonic; next new card gets id 2)
default_card_id  | 1     | default card
next_id          | 1     | transaction id counter (monotonic)
```
> `app.expense_card_id` (remembered card for Expense) is **auto-created** by the bot
> when you pick a card — do not add it manually.

**`Transactions`** — row 1 header, data empty for now:
```
id | card_id | date | amount | description | category | deleted | input_at
```

> `cycle_label` is **not stored** — it is computed on-read from `date` + the card's `cutoff_day`. There is no such column in the sheet.

> ⚠️ Header names must match exactly. If you are renaming an existing sheet's headers, update the header row manually (the code reads columns by these names).

## 4. Deploy to Vercel

1. Push the project to a repo and deploy it on Vercel.
2. Set env vars under **Settings → Environment Variables** (glossary below).
3. Register the webhook (URL: `https://<project>.vercel.app/api/webhook`):

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://<PROJECT>.vercel.app/api/webhook&secret_token=<WEBHOOK_SECRET>"
```

4. Verify:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```
`"ok": true` + `pending_update_count: 0` = ready.

5. Send `/help` in Telegram → you get a reply.

## 5. Environment variables glossary

| Variable | Where it comes from | How to get it |
|---|---|---|
| `BOT_TOKEN` | **@BotFather** | The token BotFather gives after `/newbot` (step 0) |
| `SPREADSHEET_ID` | **Google Sheets** | The long ID in the spreadsheet URL: `https://docs.google.com/spreadsheets/d/<THIS-PART>/edit` |
| `GOOGLE_CREDENTIALS_JSON` | **Google Cloud Console** | Full JSON content of the service account key file (step 2) |
| `TELEGRAM_USER_ID` | **Telegram** | Your numeric user id — send `/start` to **@userinfobot**, or print it from any Telegram client |
| `WEBHOOK_SECRET` | **You choose** | Any random secret string. Must match the `secret_token` in the `setWebhook` URL. Guards against spoofed updates |
| `APP_VERSION` *(optional)* | **You choose** | Any string to mark a deploy in the logs (default `1.0.0`) |

> `BOT_TOKEN` = bot identity (sends messages). `WEBHOOK_SECRET` = request authenticity (only accept Telegram's calls). They are two different secrets — do not reuse one for the other.

---

Continue to usage: [`docs/USAGE.md`](USAGE.md) · back to [README](../README.md)
