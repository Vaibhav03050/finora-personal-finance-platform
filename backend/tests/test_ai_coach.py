"""Tests for the deterministic AI coach template matching. These specifically
guard against the coach's own suggested prompts failing to match any
keyword bucket and silently falling through to the generic fallback -
a real bug found during manual testing (verb-tense mismatches like
'spending increase' vs 'spending increased')."""
from app.services.ai_coach import _template_answer

GENERIC_FALLBACK = "I can help with your spending, savings, and goals"


def test_where_did_my_money_go_matches():
    ctx = {"top_categories": [{"category": "Shopping", "average_monthly_minor": 150000}]}
    answer = _template_answer("Where did my money go?", ctx)
    assert GENERIC_FALLBACK not in answer
    assert "Shopping" in answer


def test_how_can_i_save_more_matches():
    ctx = {"savings_rate": 0.1}
    answer = _template_answer("How can I save more?", ctx)
    assert GENERIC_FALLBACK not in answer


def test_am_i_on_track_for_my_goal_matches():
    ctx = {"goal_status": "on_track"}
    answer = _template_answer("Am I on track for my goal?", ctx)
    assert GENERIC_FALLBACK not in answer
    assert "on track" in answer.lower()


def test_why_did_my_spending_increase_matches():
    ctx = {"increasing_categories": [{"category": "Shopping", "change_pct": 35.0}]}
    answer = _template_answer("Why did my spending increase?", ctx)
    assert GENERIC_FALLBACK not in answer
    assert "Shopping" in answer


def test_what_should_i_learn_about_investing_matches():
    ctx = {}
    answer = _template_answer("What should I learn about investing?", ctx)
    assert GENERIC_FALLBACK not in answer
    assert "not personalized investment advice" in answer.lower() or "isn't personalized" in answer.lower()


def test_all_five_suggested_prompts_never_hit_generic_fallback():
    """Every prompt shown as a clickable suggestion in the UI must produce
    a substantive answer, not the generic fallback message."""
    prompts = [
        "Where did my money go?",
        "How can I save more?",
        "Am I on track for my goal?",
        "Why did my spending increase?",
        "What should I learn about investing?",
    ]
    ctx = {
        "savings_rate": 0.15,
        "top_categories": [{"category": "Food", "average_monthly_minor": 700000}],
        "increasing_categories": [{"category": "Food", "change_pct": 20.0}],
        "goal_status": "behind",
        "shortfall_reason": "Food increased.",
    }
    for prompt in prompts:
        answer = _template_answer(prompt, ctx)
        assert GENERIC_FALLBACK not in answer, f"Prompt '{prompt}' hit the generic fallback"


def test_percentage_formatting_avoids_awkward_decimal_for_whole_numbers():
    ctx = {"increasing_categories": [{"category": "Shopping", "change_pct": 1025.0}]}
    answer = _template_answer("What increased?", ctx)
    assert "1025.0%" not in answer  # should render as "1025%", not "1025.0%"
    assert "1025%" in answer


def test_emergency_fund_question_answers_educationally():
    answer = _template_answer("What is an emergency fund?", {})
    assert "emergency" in answer.lower()
    assert GENERIC_FALLBACK not in answer


def test_sip_question_answers_educationally():
    answer = _template_answer("What is SIP?", {})
    assert "systematic investment" in answer.lower()


def test_afford_question_with_no_goal_context_asks_for_goal():
    answer = _template_answer("Can I afford a laptop?", {})
    assert "goal" in answer.lower()


def test_afford_question_with_positive_gap_says_needs_more():
    answer = _template_answer("Can I afford this?", {"goal_gap_minor": 500000})
    assert "more" in answer.lower()


def test_afford_question_with_zero_gap_says_achievable():
    answer = _template_answer("Can I afford this?", {"goal_gap_minor": 0})
    assert "achievable" in answer.lower()


def test_completely_unrelated_question_hits_generic_fallback():
    answer = _template_answer("What's the weather today?", {})
    assert GENERIC_FALLBACK in answer


# --- Free-text / open-ended question support -----------------------------
# Regression guard for the bug where any personal-finance question outside
# the hardcoded suggestion buckets fell through to the generic capability
# message instead of being answered.
import pytest

from app.services.ai_coach import _looks_finance_related, answer

OFF_TOPIC_MARKER = "outside what I cover"


@pytest.mark.parametrize(
    "question,expected_substring",
    [
        ("What is the difference between a savings account and a fixed deposit?", "fixed deposit"),
        ("How can I improve my credit score?", "credit score"),
        ("What is compound interest?", "compound"),
        ("How does compound interest work?", "compound"),
        ("What is the difference between a debit card and a credit card?", "debit card"),
        ("Explain mutual funds in simple words.", "mutual fund"),
        ("What is an SIP?", "systematic investment"),
        ("Should I create an emergency fund?", "emergency"),
        ("What is inflation?", "inflation"),
        ("How does EMI work?", "emi"),
        ("Should I buy term insurance?", "insurance"),
        ("What is net worth?", "net worth"),
        ("How can I reduce unnecessary spending?", "spend"),
    ],
)
def test_free_text_finance_questions_are_answered(question, expected_substring):
    result = _template_answer(question, {})
    assert GENERIC_FALLBACK not in result, f"'{question}' hit the generic fallback"
    assert OFF_TOPIC_MARKER not in result, f"'{question}' was wrongly treated as off-topic"
    assert expected_substring in result.lower()


@pytest.mark.parametrize(
    "question",
    [
        "Who won yesterday's cricket match?",
        "Tell me a joke",
        "What is the capital of France?",
    ],
)
def test_unrelated_questions_get_polite_off_topic_reply(question):
    result = _template_answer(question, {})
    assert OFF_TOPIC_MARKER in result
    # The off-topic reply should still point the user at what the coach does.
    assert "spending" in result.lower()


def test_coach_example_prompt_about_cutting_spend_is_answered():
    """'Where can I cut ₹2,000 this month?' is shown in the UI as an example,
    so it must never fall through to the generic fallback."""
    with_data = _template_answer(
        "Where can I cut ₹2,000 this month?",
        {"top_categories": [{"category": "Food", "average_monthly_minor": 700000}]},
    )
    assert GENERIC_FALLBACK not in with_data
    assert "Food" in with_data

    without_data = _template_answer("Where can I cut ₹2,000 this month?", {})
    assert GENERIC_FALLBACK not in without_data


def test_empty_question_returns_prompt_instead_of_failing():
    result = answer("", {})
    assert result["source"] == "template"
    assert result["answer"].strip()


def test_very_long_question_is_handled_safely():
    result = answer("How can I improve my credit score? " * 500, {})
    assert result["answer"].strip()


def test_finance_relevance_detection():
    assert _looks_finance_related("how do I budget my salary")
    assert _looks_finance_related("Where can I cut ₹2,000?")
    assert not _looks_finance_related("who won the cricket match")


def test_general_saving_question_gives_guidance_without_a_goal():
    result = _template_answer("How much should I save every month?", {})
    assert GENERIC_FALLBACK not in result
    assert "20%" in result or "goal" in result.lower()
