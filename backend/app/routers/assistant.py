from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import get_current_user
from app.database import get_session
from app.models import Goal, Transaction, User
from app.schemas import AssistantQuery, ok
from app.services import ai_coach, finance, goals as goals_service
from app.services.money import to_major

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])

SUGGESTED_PROMPTS = [
    "Where did my money go?",
    "How can I save more?",
    "Am I on track for my goal?",
    "Why did my spending increase?",
    "What should I learn about investing?",
]


def _build_context(user: User, session: Session) -> dict:
    txns = session.exec(select(Transaction).where(Transaction.user_id == user.id)).all()
    summary = finance.summarize(txns)
    tops = finance.top_spending_categories(txns, limit=5)
    trends = finance.category_trend(txns)
    increasing = [t for t in trends if t["trend"] == "increasing"]

    context = {
        "savings_rate": summary["savings_rate"],
        "top_categories": [{"category": t["category"], "average_monthly_minor": t["average_monthly_minor"]} for t in tops],
        "increasing_categories": increasing,
    }

    # Attach the most recently created active goal, if any
    goal = session.exec(select(Goal).where(Goal.user_id == user.id, Goal.achieved == False).order_by(Goal.created_at.desc())).first()
    if goal:
        avgs = finance.category_averages(txns, months=3)
        plan = goals_service.compute_goal_plan(goal, avgs)
        if plan["status"] == "in_progress":
            current_month = date.today().strftime("%Y-%m")
            this_month = [t for t in txns if t.txn_date.strftime("%Y-%m") == current_month]
            income = sum(t.amount_minor for t in this_month if (t.txn_type.value if hasattr(t.txn_type, "value") else t.txn_type) == "income")
            expense = sum(t.amount_minor for t in this_month if (t.txn_type.value if hasattr(t.txn_type, "value") else t.txn_type) == "expense")
            actual = income - expense
            status = goals_service.compute_goal_status(plan["required_monthly_minor"], actual)
            shortfall = max(plan["required_monthly_minor"] - actual, 0)
            context.update({
                "required_monthly_minor": plan["required_monthly_minor"],
                "goal_gap_minor": plan["gap_minor"],
                "goal_status": status,
                "shortfall_reason": goals_service.explain_shortfall(trends, shortfall) if status in ("behind", "slightly_behind") else "",
            })
    return context


@router.get("/prompts")
def prompts():
    return ok(SUGGESTED_PROMPTS)


@router.post("/ask")
def ask(payload: AssistantQuery, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    context = _build_context(user, session)
    result = ai_coach.answer(payload.question, context)
    return ok(result)
