from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import get_current_user
from app.database import get_session
from app.models import Goal, Transaction, User
from app.schemas import GoalCreate, GoalUpdate, ok
from app.services.finance import category_averages, category_trend
from app.services.goals import compute_goal_plan, compute_goal_status, explain_shortfall
from app.services.money import to_major, to_minor

router = APIRouter(prefix="/api/v1/goals", tags=["goals"])


def _goal_out(g: Goal) -> dict:
    return {
        "id": g.id, "name": g.name, "category": g.category,
        "target_amount_rupees": to_major(g.target_amount_minor),
        "target_date": g.target_date.isoformat(),
        "current_saved_rupees": to_major(g.current_saved_minor),
        "achieved": g.achieved,
    }


def _get_user_transactions(user_id: int, session: Session) -> list[Transaction]:
    return session.exec(select(Transaction).where(Transaction.user_id == user_id)).all()


@router.get("")
def list_goals(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    goals = session.exec(select(Goal).where(Goal.user_id == user.id)).all()
    return ok([_goal_out(g) for g in goals])


@router.post("")
def create_goal(payload: GoalCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    target_minor = to_minor(payload.target_amount_rupees)
    saved_minor = to_minor(payload.current_saved_rupees)
    goal = Goal(
        user_id=user.id, name=payload.name, category=payload.category,
        target_amount_minor=target_minor,
        target_date=payload.target_date,
        current_saved_minor=saved_minor,
        achieved=saved_minor >= target_minor,
    )
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return ok(_goal_out(goal))


@router.put("/{goal_id}")
def update_goal(goal_id: int, payload: GoalUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    goal = session.get(Goal, goal_id)
    if not goal or goal.user_id != user.id:
        raise HTTPException(status_code=404, detail="Goal not found")

    if payload.name is not None:
        goal.name = payload.name
    if payload.target_amount_rupees is not None:
        goal.target_amount_minor = to_minor(payload.target_amount_rupees)
    if payload.target_date is not None:
        goal.target_date = payload.target_date
    if payload.current_saved_rupees is not None:
        goal.current_saved_minor = to_minor(payload.current_saved_rupees)
    goal.achieved = goal.current_saved_minor >= goal.target_amount_minor

    session.add(goal)
    session.commit()
    session.refresh(goal)
    return ok(_goal_out(goal))


@router.delete("/{goal_id}")
def delete_goal(goal_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    goal = session.get(Goal, goal_id)
    if not goal or goal.user_id != user.id:
        raise HTTPException(status_code=404, detail="Goal not found")
    session.delete(goal)
    session.commit()
    return ok({"deleted": True})


@router.get("/{goal_id}/plan")
def get_goal_plan(goal_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    goal = session.get(Goal, goal_id)
    if not goal or goal.user_id != user.id:
        raise HTTPException(status_code=404, detail="Goal not found")

    transactions = _get_user_transactions(user.id, session)
    avgs = category_averages(transactions, months=3)
    plan = compute_goal_plan(goal, avgs)

    # Actual saving pace this month, to compute live status
    trends = category_trend(transactions)
    current_month = date.today().strftime("%Y-%m")
    this_month_txns = [t for t in transactions if t.txn_date.strftime("%Y-%m") == current_month]
    income = sum(t.amount_minor for t in this_month_txns if (t.txn_type.value if hasattr(t.txn_type, "value") else t.txn_type) == "income")
    expense = sum(t.amount_minor for t in this_month_txns if (t.txn_type.value if hasattr(t.txn_type, "value") else t.txn_type) == "expense")
    actual_saving = income - expense

    status = plan["status"]
    shortfall_reason = ""
    if status == "in_progress":
        live_status = compute_goal_status(plan["required_monthly_minor"], actual_saving)
        shortfall = max(plan["required_monthly_minor"] - actual_saving, 0)
        if live_status in ("behind", "slightly_behind"):
            shortfall_reason = explain_shortfall(trends, shortfall)
        status = live_status

    plan_out = {
        (k[:-len("_minor")] + "_rupees" if k.endswith("_minor") else k): (to_major(v) if k.endswith("_minor") else v)
        for k, v in plan.items() if k != "suggestions"
    }

    return ok({
        **plan_out,
        "suggestions": [
            {
                "category": s["category"],
                "current_average_rupees": to_major(s["current_average_minor"]),
                "suggested_target_rupees": to_major(s["suggested_target_minor"]),
                "potential_saving_rupees": to_major(s["potential_saving_minor"]),
            } for s in plan["suggestions"]
        ],
        "live_status": status,
        "actual_saving_this_month_rupees": to_major(actual_saving),
        "shortfall_reason": shortfall_reason,
    })
