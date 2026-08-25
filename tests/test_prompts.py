from core import prompts


def test_all_prompts_unique():
    assert len(set(prompts.ALL_PROMPTS)) == len(prompts.ALL_PROMPTS)


def test_no_prompt_is_substring_of_another():
    # Exact-match routing breaks if one prompt can appear inside another.
    for a in prompts.ALL_PROMPTS:
        for b in prompts.ALL_PROMPTS:
            if a is not b:
                assert a not in b


def test_prompts_are_nonempty_exact_strings():
    for p in prompts.ALL_PROMPTS:
        assert isinstance(p, str)
        assert p.strip()


def test_expense_prompt_shows_batch_hint():
    assert "batch" in prompts.PROMPT_EXPENSE_INPUT


def test_statement_and_running_prompts_distinct():
    assert prompts.PROMPT_STATEMENT_MONTH != prompts.PROMPT_RUNNING_MONTH
