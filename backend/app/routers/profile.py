from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import get_current_user
from app.database import get_session
from app.models import FinancialProfile, User
from app.schemas import ProfileEstimate, ok
from app.services.money import to_major, to_minor

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


@router.get("")
def get_profile(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    profile = session.exec(select(FinancialProfile).where(FinancialProfile.user_id == user.id)).first()
    if not profile:
        return ok(None)
    return ok({
        "monthly_income_rupees": to_major(profile.monthly_income_minor),
        "fixed_expenses_rupees": to_major(profile.fixed_expenses_minor),
        "lifestyle_expenses_rupees": to_major(profile.lifestyle_expenses_minor),
        "debt_emi_rupees": to_major(profile.debt_emi_minor),
        "existing_savings_rupees": to_major(profile.existing_savings_minor),
        "emergency_savings_rupees": to_major(profile.emergency_savings_minor),
        "is_estimate": profile.is_estimate,
    })


@router.post("/estimate")
def set_estimate(payload: ProfileEstimate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """Beginner mode: store an approximate financial picture with no transaction history required."""
    profile = session.exec(select(FinancialProfile).where(FinancialProfile.user_id == user.id)).first()
    if not profile:
        profile = FinancialProfile(user_id=user.id)

    profile.monthly_income_minor = to_minor(payload.monthly_income_rupees)
    profile.fixed_expenses_minor = to_minor(payload.fixed_expenses_rupees)
    profile.lifestyle_expenses_minor = to_minor(payload.lifestyle_expenses_rupees)
    profile.debt_emi_minor = to_minor(payload.debt_emi_rupees)
    profile.existing_savings_minor = to_minor(payload.existing_savings_rupees)
    profile.emergency_savings_minor = to_minor(payload.emergency_savings_rupees)
    profile.is_estimate = True

    user.is_beginner = True
    session.add(profile)
    session.add(user)
    session.commit()

    return ok({
        "message": "This is an estimate based on the information you provided. "
                    "Your recommendations will become more accurate as you track real expenses.",
        "is_estimate": True,
    })


QUIZ_QUESTIONS = [
    {"id": "money_left", "text": "Do you usually have money left at month end?"},
    {"id": "emergency_fund", "text": "Do you have emergency savings set aside?"},
    {"id": "debt", "text": "Do you have any debt or EMIs?"},
    {"id": "regular_saving", "text": "Do you regularly save some money each month?"},
    {"id": "track_expenses", "text": "Do you track your expenses in any way?"},
    {"id": "has_goal", "text": "Do you have a specific financial goal in mind?"},
]


@router.get("/quiz")
def get_quiz():
    return ok(QUIZ_QUESTIONS)


@router.post("/quiz")
def submit_quiz(answers: dict[str, bool], user: User = Depends(get_current_user)):
    """Deterministic beginner scoring - transparent, not a black box."""
    score = 40
    breakdown = []

    def add(cond_true_points, cond_false_points, key, label):
        nonlocal score
        val = answers.get(key, False)
        pts = cond_true_points if val else cond_false_points
        score_change = pts
        breakdown.append({"question": label, "answer": val, "points": pts})
        return score_change

    score += add(15, -5, "money_left", "Money left over at month end")
    score += add(15, -10, "emergency_fund", "Emergency savings set aside")
    score += add(-10, 5, "debt", "Debt / EMI burden")
    score += add(15, -5, "regular_saving", "Regularly saving")
    score += add(10, -5, "track_expenses", "Tracking expenses")
    score += add(10, 0, "has_goal", "Has a financial goal")

    score = max(0, min(100, score))

    biggest_gap = None
    if not answers.get("emergency_fund", False):
        biggest_gap = "Your biggest opportunity is building an emergency fund."
    elif not answers.get("track_expenses", False):
        biggest_gap = "Your biggest opportunity is starting to track your expenses."
    elif not answers.get("regular_saving", False):
        biggest_gap = "Your biggest opportunity is building a regular saving habit."
    elif not answers.get("has_goal", False):
        biggest_gap = "Your biggest opportunity is setting a clear financial goal."
    else:
        biggest_gap = "You're covering the fundamentals well - keep it up!"

    return ok({"starting_score": score, "breakdown": breakdown, "biggest_opportunity": biggest_gap})
