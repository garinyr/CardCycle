# CardCycle — How to Use

CardCycle is a Telegram bot that keeps track of your **credit card spending**
and tells you how much of each card's limit you have used. You control it with
the button menu at the bottom of the chat — no commands to remember.

## The menu

```
💳 Expense   📄 Statement
📊 Running   🗂 Cards
📊 Summary   ℹ️ Help
```

| Button | What it does |
|---|---|
| 💳 Expense | Record a purchase (you type the amount + note) |
| 📄 Statement | See a finished monthly bill (the one that was already issued) |
| 📊 Running | See the bill that is still building up this month |
| 🗂 Cards | See all your cards; add one; change default/limit/cutoff |
| 📊 Summary | One line per card: how much used, in one view |
| ℹ️ Help | Re-shows this menu |

A card's **limit** is changed inside Cards (tap the card's Limit button) —
no separate button needed.

The menu stays on screen after every reply. If you have more than one card,
the ⭐ marks your **main (default) card** — the one used when you don't say
otherwise.

---

## Record spending — 💳 Expense

Tap **Expense**, then type the amount and a note for each purchase. One per
line — you can record several at once:

```
150000 Lunch
30000 Coffee
14/08 500000 Monthly shopping
```

A date at the start (`14/08`) is optional; without one, today is used. A
**refund** is just a minus:

```
-50000 Tokopedia refund
```

Write whole numbers without dots: `150000`, not `150.000`. The bot confirms
what it saved; if one line is unclear, that line is skipped and the rest are
still saved.

**More than one card?** The bot first asks *which card* — tap it, then type as
above. Your choice is remembered (`Recording to …` shown while you type) until
you pick the main card again.

---

## See a finished bill — 📄 Statement

A "statement" is one complete monthly bill: everything charged to the card
from one cutoff date to the next. Tap **Statement** and the latest finished
bill appears:

```
📄 Statement August 2026
14 July 2026 – 13 August 2026 · BNI

Total spend      : Rp 2.150.000
Transactions     : 7
Card limit       : Rp 15.000.000
Utilization      : 14.3%  🟢 Good
```

Use the buttons under the message to:
- move between the recent months,
- tap **Details** to list each purchase,
- tap **All cards** (when you have several) to switch to another card's bill.

---

## See the bill building up — 📊 Running

**Running** is the bill you are building *right now* — it is not finished yet.
Everything charged since the last cutoff appears here. After the next cutoff
passes, it becomes a normal Statement. Same buttons apply (months are only
shown under Statement; Running has just the Details toggle).

---

## Card limit

Each card's current limit is shown in its Cards row. To change it, open
**Cards** and tap the card's **Limit** button, then type the new number. The
bot shows the old → new value.

---

## Utilization — what the colors mean

Utilization = how much of your card limit you have used this bill. Below 30%
is considered healthy.

| Used | Status | Emoji |
|---|---|---|
| 0–10% | Excellent | 🟢 |
| 10–30% | Good | 🟢 |
| 30–50% | Watch | 🟡 |
| 50–75% | High | 🟠 |
| 75–100% | Very High | 🔴 |
| more than 100% | Over Limit | ⛔ |

If no limit is set yet, the bot says "Limit not set" instead of guessing.

---

## Managing your cards — 🗂 Cards

**Cards** lists every card as a tappable row (⭐ = the main/default one).
Tap a card → its actions appear (only for that card — nothing is duplicated):

- **⭐ Make main** (shown when it is not the default) — one tap, no typing.
- **🎯 Limit** — the bot asks only for the new number: `8000000`.
- **📅 Cutoff** — the bot asks only for the new day: `27`.
- **↩️ Back** returns to the card list.

The chosen card is always shown while you type (e.g. `New limit for BNI
Mastercard`), and the change is confirmed with the card's name — wrong card
becomes very hard.

To add a new card (it has no row yet), tap **➕ Add card** and type:

```
Tokopedia Card 8000000 cutoff 27
```

The *cutoff day* is the day each month when the bill is cut (usually 13).

When you write a card's name, start it with `@` and it does not need to be the
full name — `@bni` finds "BNI Mastercard". If the bot can't tell which card you
mean, it lists the possibilities and asks you to be more specific.

---

## Summary — all cards in one glance

**Summary** shows one line per active card: how much of the running bill, the
limit, and the utilization color:

```
📊 Summary — running cycle per card
BNI Mastercard ⭐: Rp 1.250.000 / Rp 15.000.000 (8.3%  🟢 Excellent)
Tokopedia Card: Rp 5.200.000 / Rp 8.000.000 (65.0%  🟠 High)
```

---

## Little rules that make typing easy

- **Dates** can be written `14/08` or `14/08/2026` (day/month). Without a year,
  the current year is used.
- **Months**, when asked, accept `feb`, `Feb`, `FEBRUARY`, `nov25` (Nov 2025).
- **Amounts**: whole numbers, thousands without dots: `150000`.
- **Card names**: you only type a card name when a text needs it — e.g.
  viewing an older month of another card: `@tokopedia sep26`. Default/Limit/
  Cutoff are button flows now (no card-name typing).
- To look at another card's older bill while typing, include the card before
  the month: `@tokopedia sep26`.

## Coming later

Payment tracking, a reminder a few days before the due date, spending
categories, and editing/deleting a transaction — none of these exist yet.

---

Install & setup: [`SETUP.md`](SETUP.md) · project overview: [README](../README.md)
