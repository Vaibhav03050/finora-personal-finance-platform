"""
Goal planning: required monthly savings + realistic, spending-aware
suggestions for where that money could plausibly come from.

Language discipline: we always say "potential" / "suggested" / "based on
your previous spending" - never promise a guaranteed outcome.
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from app.models import Goal
from app.services.money import safe_div

# Conservative cap on how much of a flexible/discretionary category we ever
# suggest trimming, so recommendations stay realistic rather than punitive.
MAX_REDUCTION_PCT = {
    "discretionary": 0.30,
    "flexible": 0.20,
    "essential": 0.0,   # never suggest cutting essentials
}


def months_between(today: date, target: date) -> int:
    if target <= today:
        return 0
    delta = relativedelta(target, today)
    total_months = delta.years * 12 + delta.months
    if delta.days > 0:
        total_months += 1
    return max(total_months, 1)


def compute_goal_plan(goal: Goal, category_averages: dict[str, dict], today: date = None) -> dict:
    today = today or date.today()
    remaining_minor = max(goal.target_amount_minor - goal.current_saved_minor, 0)

    if goal.current_saved_minor >= goal.target_amount_minor:
        return {
            "status": "achieved", "remaining_minor": 0, "months_remaining": 0,
            "required_monthly_minor": 0, "suggestions": [], "potential_total_minor": 0,
            "gap_minor": 0,
            "message": "This goal has already been reached.",
        }

    months_remaining = months_between(today, goal.target_date)

    if goal.target_date <= today:
        return {
            "status": "deadline_passed", "remaining_minor": remaining_minor, "months_remaining": 0,
            "required_monthly_minor": remaining_minor,  # would need it all at once
            "suggestions": [], "potential_total_minor": 0, "gap_minor": remaining_minor,
            "message": "This goal's target date has passed. Consider setting a new date.",
        }

    required_monthly_minor = round(remaining_minor / months_remaining)

    # Rank flexible/discretionary categories by spend, suggest a capped trim.
    suggestions = []
    potential_total = 0
    candidates = [
        (cat, data) for cat, data in category_averages.items()
        if data["flexibility"] in ("flexible", "discretionary") and data["average_monthly_minor"] > 0
    ]
    candidates.sort(key=lambda kv: -kv[1]["average_monthly_minor"])

    for cat, data in candidates[:4]:
        avg = data["average_monthly_minor"]
        cap_pct = MAX_REDUCTION_PCT[data["flexibility"]]
        potential_saving = round(avg * cap_pct)
        if potential_saving <= 0:
            continue
        suggested_target = avg - potential_saving
        suggestions.append({
            "category": cat,
            "current_average_minor": avg,
            "suggested_target_minor": suggested_target,
            "potential_saving_minor": potential_saving,
        })
        potential_total += potential_saving

    gap_minor = max(required_monthly_minor - potential_total, 0)

    return {
        "status": "in_progress",
        "remaining_minor": remaining_minor,
        "months_remaining": months_remaining,
        "required_monthly_minor": required_monthly_minor,
        "suggestions": suggestions,
        "potential_total_minor": potential_total,
        "gap_minor": gap_minor,
        "message": None,
    }


def compute_goal_status(
    required_monthly_minor: int,
    actual_monthly_saving_minor: int,
) -> str:
    if required_monthly_minor <= 0:
        return "on_track"
    ratio = safe_div(actual_monthly_saving_minor, required_monthly_minor)
    if ratio >= 1.1:
        return "ahead"
    if ratio >= 0.95:
        return "on_track"
    if ratio >= 0.7:
        return "slightly_behind"
    return "behind"


def explain_shortfall(category_trends: list[dict], shortfall_minor: int) -> str:
    """Plain-language explanation of why a user is behind, using trend data."""
    if shortfall_minor <= 0:
        return ""
    rising = [t for t in category_trends if t["trend"] == "increasing"]
    if not rising:
        return "Your overall spending was a bit higher than usual this month."
    parts = []
    for t in rising[:2]:
        pct = t['change_pct']
        pct_str = f"{pct:.0f}" if pct is not None and float(pct).is_integer() else f"{pct}"
        parts.append(f"{t['category']} increased by about {pct_str}%")
    return " and ".join(parts) + " compared with your normal spending."
