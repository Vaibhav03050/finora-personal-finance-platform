"""
Deterministic, explainable financial health score. Every point on the
score maps to a stated reason - no black box.
"""
from app.services.money import safe_div


def compute_health_score(
    monthly_income_minor: int,
    monthly_expense_minor: int,
    emergency_savings_minor: int,
    debt_emi_minor: int,
    savings_rate: float,
) -> dict:
    breakdown = []
    score = 50  # neutral baseline

    # --- Savings rate (up to +25 / -15) ---
    if savings_rate >= 0.30:
        pts, note = 25, "Excellent savings rate (30%+ of income saved)."
    elif savings_rate >= 0.20:
        pts, note = 18, "Good savings rate (20-30% of income saved)."
    elif savings_rate >= 0.10:
        pts, note = 8, "Fair savings rate (10-20% of income saved)."
    elif savings_rate >= 0:
        pts, note = -5, "Low savings rate (under 10% of income saved)."
    else:
        pts, note = -15, "You are spending more than you earn this period."
    breakdown.append({"label": "Savings rate", "points": pts, "reason": note})
    score += pts

    # --- Expense-to-income ratio (up to +15 / -15) ---
    ratio = safe_div(monthly_expense_minor, monthly_income_minor) if monthly_income_minor else 1.0
    if ratio <= 0.5:
        pts, note = 15, "Your regular expenses are a healthy share of your income."
    elif ratio <= 0.7:
        pts, note = 8, "Your expenses are moderate relative to your income."
    elif ratio <= 0.9:
        pts, note = -5, "Your expenses take up most of your income."
    else:
        pts, note = -15, "Your expenses are close to or above your income."
    breakdown.append({"label": "Expense-to-income ratio", "points": pts, "reason": note})
    score += pts

    # --- Emergency fund coverage in months of expenses (up to +20 / -10) ---
    months_covered = safe_div(emergency_savings_minor, monthly_expense_minor) if monthly_expense_minor else 0
    if months_covered >= 6:
        pts, note = 20, "You have 6+ months of expenses set aside for emergencies."
    elif months_covered >= 3:
        pts, note = 12, "You have 3-6 months of emergency savings - a solid cushion."
    elif months_covered >= 1:
        pts, note = 2, "You have a small emergency cushion (1-3 months)."
    else:
        pts, note = -10, "Emergency fund needs improvement - build 3+ months of expenses."
    breakdown.append({"label": "Emergency fund", "points": pts, "reason": note})
    score += pts

    # --- Debt/EMI burden (up to +5 / -15) ---
    debt_ratio = safe_div(debt_emi_minor, monthly_income_minor) if monthly_income_minor else 0
    if debt_ratio == 0:
        pts, note = 5, "You have no reported debt/EMI burden."
    elif debt_ratio <= 0.2:
        pts, note = 2, "Your debt/EMI burden is manageable relative to income."
    elif debt_ratio <= 0.4:
        pts, note = -8, "Your debt/EMI burden is on the higher side."
    else:
        pts, note = -15, "Debt/EMI payments are a large share of your income."
    breakdown.append({"label": "Debt/EMI burden", "points": pts, "reason": note})
    score += pts

    score = max(0, min(100, round(score)))

    if score >= 80:
        tier, emoji = "Excellent", "💚"
    elif score >= 60:
        tier, emoji = "Good", "💛"
    elif score >= 40:
        tier, emoji = "Needs attention", "🧡"
    else:
        tier, emoji = "At risk", "❤️"

    return {"score": score, "tier": tier, "emoji": emoji, "breakdown": breakdown}
