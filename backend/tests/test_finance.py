import sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import Transaction
from app.services import finance


def make_txn(txn_date, amount_minor, txn_type, category="Other", merchant=""):
    return Transaction(
        user_id=1, txn_date=txn_date, merchant=merchant, description=merchant,
        amount_minor=amount_minor, currency="INR", txn_type=txn_type, category=category,
        dedupe_hash="x",
    )


# ---------- summarize() ----------

def test_summarize_no_transactions():
    result = finance.summarize([])
    assert result["total_income_minor"] == 0
    assert result["total_expense_minor"] == 0
    assert result["savings_minor"] == 0
    assert result["savings_rate"] == 0.0


def test_summarize_income_zero_but_has_expense():
    txns = [make_txn(date(2026, 1, 5), 50000, "expense", "Food")]
    result = finance.summarize(txns)
    assert result["total_income_minor"] == 0
    assert result["total_expense_minor"] == 50000
    assert result["savings_minor"] == -50000
    # income == 0 must not raise a ZeroDivisionError
    assert result["savings_rate"] == 0.0


def test_summarize_expense_exceeds_income():
    txns = [
        make_txn(date(2026, 1, 1), 100000, "income", "Income"),
        make_txn(date(2026, 1, 5), 150000, "expense", "Shopping"),
    ]
    result = finance.summarize(txns)
    assert result["savings_minor"] == -50000
    assert result["savings_rate"] < 0


def test_summarize_normal_case():
    txns = [
        make_txn(date(2026, 1, 1), 5000000, "income", "Income"),  # 50,000
        make_txn(date(2026, 1, 5), 1000000, "expense", "Food"),   # 10,000
        make_txn(date(2026, 1, 6), 500000, "expense", "Shopping"),  # 5,000
    ]
    result = finance.summarize(txns)
    assert result["total_income_minor"] == 5000000
    assert result["total_expense_minor"] == 1500000
    assert result["savings_minor"] == 3500000
    assert result["savings_rate"] == 0.7


def test_summarize_single_transaction():
    txns = [make_txn(date(2026, 1, 1), 100000, "income", "Income")]
    result = finance.summarize(txns)
    assert result["num_transactions"] == 1
    assert result["savings_rate"] == 1.0


# ---------- category_averages() ----------

def test_category_averages_empty():
    assert finance.category_averages([]) == {}


def test_category_averages_only_income_returns_empty():
    txns = [make_txn(date(2026, 1, 1), 100000, "income", "Income")]
    assert finance.category_averages(txns) == {}


def test_category_averages_flexibility_tagging():
    txns = [
        make_txn(date(2026, 1, 5), 300000, "expense", "Shopping"),
        make_txn(date(2026, 1, 6), 200000, "expense", "Bills"),
    ]
    avgs = finance.category_averages(txns, months=1)
    assert avgs["Shopping"]["flexibility"] == "discretionary"
    assert avgs["Bills"]["flexibility"] == "essential"


def test_category_averages_very_large_amount_does_not_overflow():
    txns = [make_txn(date(2026, 1, 1), 10_000_000_000, "expense", "Shopping")]
    avgs = finance.category_averages(txns, months=1)
    assert avgs["Shopping"]["average_monthly_minor"] == 10_000_000_000


# ---------- category_trend() ----------

def test_category_trend_insufficient_data_single_month():
    txns = [make_txn(date(2026, 1, 5), 100000, "expense", "Food")]
    trends = finance.category_trend(txns)
    assert trends[0]["trend"] == "insufficient_data"


def test_category_trend_detects_increase():
    txns = [
        make_txn(date(2025, 12, 5), 100000, "expense", "Shopping"),  # prior month baseline
        make_txn(date(2026, 1, 5), 200000, "expense", "Shopping"),   # latest month: +100%
    ]
    trends = finance.category_trend(txns)
    shopping = next(t for t in trends if t["category"] == "Shopping")
    assert shopping["trend"] == "increasing"
    assert shopping["change_pct"] == 100.0


def test_category_trend_stable():
    txns = [
        make_txn(date(2025, 12, 5), 100000, "expense", "Food"),
        make_txn(date(2026, 1, 5), 105000, "expense", "Food"),  # +5%, within stable band
    ]
    trends = finance.category_trend(txns)
    food = next(t for t in trends if t["category"] == "Food")
    assert food["trend"] == "stable"


# ---------- recurring_expenses() ----------

def test_recurring_expenses_detects_consistent_subscription():
    txns = [
        make_txn(date(2025, 11, 1), 49900, "expense", "Entertainment", merchant="Netflix"),
        make_txn(date(2025, 12, 1), 49900, "expense", "Entertainment", merchant="Netflix"),
        make_txn(date(2026, 1, 1), 49900, "expense", "Entertainment", merchant="Netflix"),
    ]
    recurring = finance.recurring_expenses(txns)
    assert len(recurring) == 1
    assert recurring[0]["merchant"] == "Netflix"
    assert recurring[0]["occurrences"] == 3


def test_recurring_expenses_ignores_one_off_merchant():
    txns = [make_txn(date(2026, 1, 1), 49900, "expense", "Shopping", merchant="RandomStore")]
    assert finance.recurring_expenses(txns) == []


def test_recurring_expenses_ignores_inconsistent_amounts():
    txns = [
        make_txn(date(2025, 12, 1), 10000, "expense", "Food", merchant="Cafe"),
        make_txn(date(2026, 1, 1), 90000, "expense", "Food", merchant="Cafe"),  # wildly different
    ]
    assert finance.recurring_expenses(txns) == []
