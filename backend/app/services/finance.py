"""
Deterministic financial analytics.

Rule: money math is deterministic, tested, and lives here. The AI coach
layer only ever explains numbers computed by these functions - it never
computes them itself.
"""
from collections import defaultdict
from datetime import date
from typing import Iterable

import pandas as pd

from app.models import Transaction
from app.services.categorize import DISCRETIONARY_CATEGORIES, ESSENTIAL_CATEGORIES, FLEXIBLE_CATEGORIES
from app.services.money import safe_div


def _to_dataframe(transactions: Iterable[Transaction]) -> pd.DataFrame:
    rows = [{
        "date": t.txn_date, "amount_minor": t.amount_minor, "type": t.txn_type.value if hasattr(t.txn_type, "value") else t.txn_type,
        "category": t.category, "merchant": t.merchant,
        "month": t.txn_date.strftime("%Y-%m"),
    } for t in transactions]
    return pd.DataFrame(rows, columns=["date", "amount_minor", "type", "category", "merchant", "month"])


def summarize(transactions: list[Transaction]) -> dict:
    """Total income, total expense, savings, savings rate across all provided transactions."""
    if not transactions:
        return {
            "total_income_minor": 0, "total_expense_minor": 0,
            "savings_minor": 0, "savings_rate": 0.0, "num_transactions": 0,
        }
    df = _to_dataframe(transactions)
    income = int(df.loc[df["type"] == "income", "amount_minor"].sum())
    expense = int(df.loc[df["type"] == "expense", "amount_minor"].sum())
    savings = income - expense
    savings_rate = safe_div(savings, income) if income > 0 else 0.0
    return {
        "total_income_minor": income,
        "total_expense_minor": expense,
        "savings_minor": savings,
        "savings_rate": round(savings_rate, 4),
        "num_transactions": len(transactions),
    }


def monthly_breakdown(transactions: list[Transaction]) -> list[dict]:
    """Income/expense/savings per calendar month, sorted ascending by month."""
    if not transactions:
        return []
    df = _to_dataframe(transactions)
    grouped = df.groupby(["month", "type"])["amount_minor"].sum().unstack(fill_value=0)
    result = []
    for month in sorted(grouped.index):
        income = int(grouped.loc[month].get("income", 0))
        expense = int(grouped.loc[month].get("expense", 0))
        result.append({
            "month": month, "income_minor": income, "expense_minor": expense,
            "savings_minor": income - expense,
        })
    return result


def category_averages(transactions: list[Transaction], months: int = 3) -> dict[str, dict]:
    """
    Average monthly spend per expense category, over the last `months`
    calendar months present in the data. Used for goal-planning suggestions.
    """
    expense_txns = [t for t in transactions if (t.txn_type.value if hasattr(t.txn_type, "value") else t.txn_type) == "expense"]
    if not expense_txns:
        return {}
    df = _to_dataframe(expense_txns)
    recent_months = sorted(df["month"].unique())[-months:]
    df = df[df["month"].isin(recent_months)]
    n_months = max(len(recent_months), 1)

    result = {}
    for category, group in df.groupby("category"):
        total = int(group["amount_minor"].sum())
        avg = round(total / n_months)
        result[category] = {
            "average_monthly_minor": avg,
            "total_minor": total,
            "flexibility": _flexibility(category),
        }
    return result


def _flexibility(category: str) -> str:
    if category in ESSENTIAL_CATEGORIES:
        return "essential"
    if category in FLEXIBLE_CATEGORIES:
        return "flexible"
    return "discretionary"


def category_trend(transactions: list[Transaction]) -> list[dict]:
    """
    Compare each category's most recent month vs the average of prior months
    to flag increasing / decreasing / stable spending.
    """
    expense_txns = [t for t in transactions if (t.txn_type.value if hasattr(t.txn_type, "value") else t.txn_type) == "expense"]
    if not expense_txns:
        return []
    df = _to_dataframe(expense_txns)
    months = sorted(df["month"].unique())
    if len(months) < 2:
        return [{
            "category": cat, "trend": "insufficient_data", "change_pct": None,
        } for cat in df["category"].unique()]

    latest_month = months[-1]
    prior_months = months[:-1]

    out = []
    for category, group in df.groupby("category"):
        latest = int(group.loc[group["month"] == latest_month, "amount_minor"].sum())
        prior_vals = [
            int(group.loc[group["month"] == m, "amount_minor"].sum())
            for m in prior_months
        ]
        prior_avg = safe_div(sum(prior_vals), len(prior_vals)) if prior_vals else 0
        if prior_avg == 0:
            trend, change_pct = ("new_spending" if latest > 0 else "stable"), None
        else:
            change_pct = round(((latest - prior_avg) / prior_avg) * 100, 1)
            if change_pct > 15:
                trend = "increasing"
            elif change_pct < -15:
                trend = "decreasing"
            else:
                trend = "stable"
        out.append({
            "category": category, "trend": trend, "change_pct": change_pct,
            "latest_month_minor": latest, "prior_avg_minor": round(prior_avg),
        })
    return sorted(out, key=lambda x: -(x["latest_month_minor"]))


def recurring_expenses(transactions: list[Transaction], tolerance_pct: float = 0.1) -> list[dict]:
    """
    Detect merchants that recur across 2+ distinct months with a similar
    amount each time (candidate subscriptions / recurring bills).
    """
    expense_txns = [t for t in transactions if (t.txn_type.value if hasattr(t.txn_type, "value") else t.txn_type) == "expense" and t.merchant]
    by_merchant: dict[str, list[Transaction]] = defaultdict(list)
    for t in expense_txns:
        by_merchant[t.merchant.strip().lower()].append(t)

    recurring = []
    for merchant, txns in by_merchant.items():
        months_seen = {t.txn_date.strftime("%Y-%m") for t in txns}
        if len(months_seen) < 2:
            continue
        amounts = [t.amount_minor for t in txns]
        avg = sum(amounts) / len(amounts)
        if avg == 0:
            continue
        consistent = all(abs(a - avg) / avg <= tolerance_pct for a in amounts)
        if consistent:
            recurring.append({
                "merchant": txns[0].merchant, "average_amount_minor": round(avg),
                "occurrences": len(txns), "months_seen": sorted(months_seen),
            })
    return sorted(recurring, key=lambda x: -x["average_amount_minor"])


def top_spending_categories(transactions: list[Transaction], limit: int = 5) -> list[dict]:
    averages = category_averages(transactions, months=3)
    ranked = sorted(averages.items(), key=lambda kv: -kv[1]["average_monthly_minor"])
    return [{"category": cat, **data} for cat, data in ranked[:limit]]
