# USAGE — CardCycle Buttons

> The "Bot reply" examples below are the **rendered appearance** (bold = `**bold**`, mono = `` `code` ``). Real messages are sent with `parse_mode="HTML"`.
>
> **There are no slash commands anymore.** Everything starts from the menu buttons below.

## Button menu (tap, no typing)

A **persistent reply keyboard** sits at the bottom of the chat. Tap a button instead of typing:

```
💳 Expense   📄 Statement
📊 Running   🎯 Limit
ℹ️ Help
```

| Button | What it does |
|---|---|
| 💳 Expense | Shows the format — recording needs typing (see below) |
| 📄 Statement | Latest issued (frozen) statement + utilization |
| 📊 Running | Current (running) cycle + utilization |
| 🎯 Limit | Shows the card limit |
| ℹ️ Help | Re-shows this menu |

The menu is re-sent with every reply, so it is always visible. Only **Expense** and **Limit update** need typed input (via ForceReply).

## Recording spending — needs typing

**You send:**
```
150000 Lunch
14/08 500000 Monthly shopping
30000  Coffee
```
→ `📋 Recorded: 3 saved`

**Refund (negative amount):**
```
-50000 Tokopedia refund
```

> Lines that fail to parse are reported; valid lines are still saved:
> ```
> 📋 Recorded: 1 saved, 1 failed
>
> ✅ 23/08/2026 Rp 150.000 Lunch
> ⚠️ Line 2: invalid amount: abc
> ```

## Statement — tap `📄 Statement`

Latest issued (frozen) statement:

```
📄 Statement August 2026
14 July 2026 – 13 August 2026 · BNI

Total spend      : Rp 2.150.000
Transactions     : 7
Card limit       : Rp 15.000.000
Utilization      : 14.3%  🟢 Good
```

## 📊 Running — view the current cycle

The cycle **still accumulating** — the one today's spending bills into.

```
**📄 Running** September 2026
`14 August 2026` – `13 September 2026` · BNI

Total spend      : Rp 1.250.000
Transactions     : 4
Card limit       : Rp 15.000.000
Utilization      : 8.3%  🟢 Excellent
```

- Tap `📊 Running` → the still-accumulating cycle + a single `🔍 Details` toggle.
- No month navigation here — history lives under `📄 Statement`.

> `running` = the cycle containing today (WIB). After its cutoff passes, it becomes a frozen `statement`.
> A cycle spans from the day after the previous month's cutoff through this month's cutoff.
> Example cutoff 13: February 2026 cycle = 14 Jan – 13 Feb 2026.

## 🎯 Limit — view / update

**View** — tap the button:
```
📋 **Limit BNI**
**Rp 15.000.000**
```

**Update** — type the value:
```
✅ Limit BNI updated
Rp 15.000.000 → Rp 10.000.000
```

## ℹ️ Help

Tap → re-shows the menu + a one-line cheat sheet per button. Informational only.

## Utilization & Status

`utilization = cycle_total_spend / card_limit` (if limit is unset → "Limit not set", not an error).

| Utilization | Status | Emoji |
|---|---|---|
| 0–10% | Excellent | 🟢 |
| 10–30% | Good | 🟢 |
| 30–50% | Watch | 🟡 |
| 50–75% | High | 🟠 |
| 75–100% | Very High | 🔴 |
| >100% | Over Limit | ⛔ |

## Format Notes

- **Messages use `parse_mode="HTML"`** — all user input (`description`, error messages) is auto-escaped (`<`, `>`, `&`) so it can't break markup. Aligned columns use `<pre>`.
- **Cycle label** is computed on-read: `day <= cutoff_day` → that month; `day > cutoff_day` → next month (Dec → Jan rollover). Changing the cutoff never desyncs old data.
- **Transaction `id`** comes from the `Config.next_id` counter (monotonic), not the row count — safe for future edit/delete.
- Input amounts use whole numbers without dots/commas: `150000` (not `150.000`). Dots/commas are stripped automatically if they sneak in.
- **Month** (for `📅 Other month`) is case-insensitive: `feb`, `Feb`, `FEBRUARY` all work. Year can be 2-digit (`nov25` = Nov 2025) or 4-digit (`nov2025`).
- All "today" calculations use **WIB** (`Asia/Jakarta`).
- Security: only `TELEGRAM_USER_ID` is served; requests without the correct `X-Telegram-Bot-Api-Secret-Token` get a 401.

## Future (MVP2)

Multi-card (`@name` selector, `/summary`), payment tracking (`Payments` sheet), H-3 reminder (Vercel Cron + `due_day` + `ReminderLog`), categories, edit/delete transactions.

---

Install & deploy: [`docs/SETUP.md`](SETUP.md) · back to [README](../README.md)
