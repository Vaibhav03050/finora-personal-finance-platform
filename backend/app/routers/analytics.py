from datetime import date

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import get_current_user
from app.database import get_session
from app.models import FinancialProfile, Transaction, User
from app.schemas import ok
from app.services import finance
from app.services.health_score import compute_health_score
from app.services.money import to_major

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def _txns(user_id: int, session: Session) -> list[Transaction]:
    return session.exec(select(Transaction).where(Transaction.user_id == user_id)).all()


def _minor_to_major_dict(d: dict) -> dict:
    return {
        (k[:-len("_minor")] + "_rupees" if k.endswith("_minor") else k): (to_major(v) if k.endswith("_minor") else v)
        for k, v in d.items()
    }


@router.get("/summary")
def summary(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    txns = _txns(user.id, session)
    result = finance.summarize(txns)

    if not txns:
        profile = session.exec(select(FinancialProfile).where(FinancialProfile.user_id == user.id)).first()
        if profile:
            income = profile.monthly_income_minor
            expense = profile.fixed_expenses_minor + profile.lifestyle_expenses_minor
            savings = income - expense
            result = {
                "total_income_minor": income, "total_expense_minor": expense,
                "savings_minor": savings, "savings_rate": round(savings / income, 4) if income > 0 else 0.0,
                "num_transactions": 0, "is_estimate": True,
            }
    out = _minor_to_major_dict(result)
    out["is_estimate"] = result.get("is_estimate", False)
    return ok(out)


@router.get("/monthly")
def monthly(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    rows = finance.monthly_breakdown(_txns(user.id, session))
    return ok([_minor_to_major_dict(r) for r in rows])


@router.get("/categories")
def categories(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    avgs = finance.category_averages(_txns(user.id, session))
    return ok({
        cat: {
            "average_monthly_rupees": to_major(data["average_monthly_minor"]),
            "total_rupees": to_major(data["total_minor"]),
            "flexibility": data["flexibility"],
        } for cat, data in avgs.items()
    })


@router.get("/trends")
def trends(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    rows = finance.category_trend(_txns(user.id, session))
    return ok([_minor_to_major_dict(r) for r in rows])


@router.get("/recurring")
def recurring(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    rows = finance.recurring_expenses(_txns(user.id, session))
    return ok([_minor_to_major_dict(r) for r in rows])


@router.get("/save-suggestions")
def save_suggestions(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """'Where can I save money next month?' - ranked, trend-aware, essential/flexible separated."""
    txns = _txns(user.id, session)
    tops = finance.top_spending_categories(txns, limit=6)
    trend_rows = {t["category"]: t for t in finance.category_trend(txns)}

    suggestions = []
    for item in tops:
        if item["flexibility"] == "essential":
            continue
        trend = trend_rows.get(item["category"], {})
        avg = item["average_monthly_minor"]
        cap = 0.30 if item["flexibility"] == "discretionary" else 0.20
        low = round(avg * cap * 0.6)
        high = round(avg * cap)
        urgency = "🔴" if trend.get("trend") == "increasing" else ("🟡" if item["flexibility"] == "discretionary" else "🟠")
        suggestions.append({
            "category": item["category"], "flexibility": item["flexibility"],
            "average_monthly_rupees": to_major(avg),
            "trend": trend.get("trend", "stable"), "change_pct": trend.get("change_pct"),
            "potential_saving_low_rupees": to_major(low), "potential_saving_high_rupees": to_major(high),
            "urgency": urgency,
        })
    return ok(suggestions)


@router.get("/financial-health")
def financial_health(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    txns = _txns(user.id, session)
    current_month = date.today().strftime("%Y-%m")
    this_month = [t for t in txns if t.txn_date.strftime("%Y-%m") == current_month]

    profile = session.exec(select(FinancialProfile).where(FinancialProfile.user_id == user.id)).first()

    if this_month:
        income = sum(t.amount_minor for t in this_month if (t.txn_type.value if hasattr(t.txn_type, "value") else t.txn_type) == "income")
        expense = sum(t.amount_minor for t in this_month if (t.txn_type.value if hasattr(t.txn_type, "value") else t.txn_type) == "expense")
    elif profile:
        income = profile.monthly_income_minor
        expense = profile.fixed_expenses_minor + profile.lifestyle_expenses_minor
    else:
        income = expense = 0

    emergency = profile.emergency_savings_minor if profile else 0
    debt = profile.debt_emi_minor if profile else 0
    savings_rate = (income - expense) / income if income > 0 else 0.0

    result = compute_health_score(income, expense, emergency, debt, savings_rate)
    result["is_estimate"] = bool(profile and profile.is_estimate and not this_month)
    return ok(result)
