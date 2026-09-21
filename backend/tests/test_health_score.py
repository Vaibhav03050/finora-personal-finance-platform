import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.health_score import compute_health_score


def test_health_score_bounded_between_0_and_100():
    result = compute_health_score(
        monthly_income_minor=0, monthly_expense_minor=10_000_000,
        emergency_savings_minor=0, debt_emi_minor=5_000_000, savings_rate=-5.0,
    )
    assert 0 <= result["score"] <= 100


def test_health_score_excellent_profile():
    result = compute_health_score(
        monthly_income_minor=10_000_000, monthly_expense_minor=4_000_000,
        emergency_savings_minor=30_000_000, debt_emi_minor=0, savings_rate=0.6,
    )
    assert result["score"] >= 80
    assert result["tier"] == "Excellent"


def test_health_score_at_risk_profile():
    result = compute_health_score(
        monthly_income_minor=5_000_000, monthly_expense_minor=6_000_000,
        emergency_savings_minor=0, debt_emi_minor=2_500_000, savings_rate=-0.2,
    )
    assert result["score"] < 40
    assert result["tier"] == "At risk"


def test_health_score_zero_income_does_not_crash():
    result = compute_health_score(
        monthly_income_minor=0, monthly_expense_minor=0,
        emergency_savings_minor=0, debt_emi_minor=0, savings_rate=0.0,
    )
    assert isinstance(result["score"], int)


def test_health_score_breakdown_has_reasons_for_every_factor():
    result = compute_health_score(
        monthly_income_minor=5_000_000, monthly_expense_minor=3_000_000,
        emergency_savings_minor=9_000_000, debt_emi_minor=500_000, savings_rate=0.4,
    )
    assert len(result["breakdown"]) == 4
    for item in result["breakdown"]:
        assert item["reason"]
        assert isinstance(item["points"], int)
