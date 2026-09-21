import sys
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import Goal
from app.services.goals import compute_goal_plan, compute_goal_status, months_between


def make_goal(target_minor, target_date, saved_minor=0):
    return Goal(
        user_id=1, name="Test Goal", category="Custom",
        target_amount_minor=target_minor, target_date=target_date, current_saved_minor=saved_minor,
    )


# ---------- months_between ----------

def test_months_between_normal():
    assert months_between(date(2026, 1, 1), date(2026, 9, 1)) == 8


def test_months_between_past_date_returns_zero():
    assert months_between(date(2026, 6, 1), date(2026, 1, 1)) == 0


def test_months_between_same_day_next_month_rounds_up_for_partial():
    # 2026-01-15 -> 2026-02-01 is less than a full month but should round up to at least 1
    assert months_between(date(2026, 1, 15), date(2026, 2, 1)) >= 1


# ---------- compute_goal_plan ----------

def test_goal_plan_already_achieved():
    goal = make_goal(target_minor=6000000, target_date=date(2026, 12, 1), saved_minor=6000000)
    plan = compute_goal_plan(goal, {}, today=date(2026, 1, 1))
    assert plan["status"] == "achieved"
    assert plan["required_monthly_minor"] == 0


def test_goal_plan_over_saved_still_achieved():
    goal = make_goal(target_minor=6000000, target_date=date(2026, 12, 1), saved_minor=7000000)
    plan = compute_goal_plan(goal, {}, today=date(2026, 1, 1))
    assert plan["status"] == "achieved"


def test_goal_plan_deadline_passed():
    goal = make_goal(target_minor=6000000, target_date=date(2025, 1, 1), saved_minor=1000000)
    plan = compute_goal_plan(goal, {}, today=date(2026, 1, 1))
    assert plan["status"] == "deadline_passed"
    assert plan["gap_minor"] == 5000000


def test_goal_plan_basic_required_monthly_matches_spec_example():
    # ₹60,000 target, ₹10,000 already saved, 8 months -> required ≈ ₹6,250/month
    goal = make_goal(target_minor=6_000_000, target_date=date(2026, 9, 1), saved_minor=1_000_000)
    plan = compute_goal_plan(goal, {}, today=date(2026, 1, 1))
    assert plan["status"] == "in_progress"
    assert plan["months_remaining"] == 8
    assert plan["required_monthly_minor"] == 625_000  # ₹6,250.00 in paise


def test_goal_plan_suggestions_never_touch_essential_categories():
    goal = make_goal(target_minor=6_000_000, target_date=date(2026, 9, 1), saved_minor=1_000_000)
    category_averages = {
        "Bills": {"average_monthly_minor": 500_000, "flexibility": "essential"},
        "Shopping": {"average_monthly_minor": 600_000, "flexibility": "discretionary"},
    }
    plan = compute_goal_plan(goal, category_averages, today=date(2026, 1, 1))
    suggested_categories = [s["category"] for s in plan["suggestions"]]
    assert "Bills" not in suggested_categories
    assert "Shopping" in suggested_categories


def test_goal_plan_suggestions_are_capped_conservatively():
    goal = make_goal(target_minor=6_000_000, target_date=date(2026, 9, 1), saved_minor=0)
    category_averages = {"Shopping": {"average_monthly_minor": 1_000_000, "flexibility": "discretionary"}}
    plan = compute_goal_plan(goal, category_averages, today=date(2026, 1, 1))
    suggestion = plan["suggestions"][0]
    # discretionary cap is 30% - potential saving should never exceed that
    assert suggestion["potential_saving_minor"] <= 300_000


def test_goal_plan_no_category_data_still_returns_required_monthly():
    goal = make_goal(target_minor=6_000_000, target_date=date(2026, 9, 1), saved_minor=0)
    plan = compute_goal_plan(goal, {}, today=date(2026, 1, 1))
    assert plan["required_monthly_minor"] > 0
    assert plan["suggestions"] == []
    assert plan["gap_minor"] == plan["required_monthly_minor"]


# ---------- compute_goal_status ----------

def test_goal_status_ahead():
    assert compute_goal_status(required_monthly_minor=100000, actual_monthly_saving_minor=150000) == "ahead"


def test_goal_status_on_track():
    assert compute_goal_status(required_monthly_minor=100000, actual_monthly_saving_minor=98000) == "on_track"


def test_goal_status_slightly_behind():
    assert compute_goal_status(required_monthly_minor=100000, actual_monthly_saving_minor=80000) == "slightly_behind"


def test_goal_status_behind():
    assert compute_goal_status(required_monthly_minor=100000, actual_monthly_saving_minor=30000) == "behind"


def test_goal_status_required_zero_is_on_track():
    assert compute_goal_status(required_monthly_minor=0, actual_monthly_saving_minor=0) == "on_track"


def test_goal_status_negative_actual_saving_is_behind():
    # user spent more than they earned this month
    assert compute_goal_status(required_monthly_minor=100000, actual_monthly_saving_minor=-50000) == "behind"
