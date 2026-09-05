"""core/prompts.py — ForceReply prompt texts (single source of truth).

The webhook routes a user's reply by exact-matching `reply_to_message.text`
against these constants. Rules:
- Exact match, never keyword/substring — so routing stays correct even if the
  wording is revised later.
- Each prompt must be unique; never make one a substring of another.
- Change a string only here, so the bot message and the reply matcher never
  desync.
"""

PROMPT_EXPENSE_INPUT = (
    "Type amount + description. Examples:\n"
    "150000 Lunch\n"
    "14/08 500000 Monthly shopping\n"
    "\n"
    "Multi-line for batch entry."
)

PROMPT_STATEMENT_MONTH = "Type a month, e.g. mar25 or november"

PROMPT_RUNNING_MONTH = "Type a running month, e.g. mar25 or november"

PROMPT_CARDS_ADD = (
    "Type the new card. Format:\n"
    "Tokopedia Card 8000000 cutoff 27\n"
    "(name + limit required; cutoff optional, default 13)"
)

PROMPT_CARDS_LIMIT = "Type the new limit, e.g. 8000000"

PROMPT_CARDS_CUTOFF = "Type the new cutoff day, e.g. 27"

# Order matters for routing: check the most specific prompts first.
ALL_PROMPTS = (
    PROMPT_EXPENSE_INPUT,
    PROMPT_STATEMENT_MONTH,
    PROMPT_RUNNING_MONTH,
    PROMPT_CARDS_ADD,
    PROMPT_CARDS_LIMIT,
    PROMPT_CARDS_CUTOFF,
)
