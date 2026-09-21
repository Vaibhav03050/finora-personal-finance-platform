import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.categorize import categorize, rule_categorize


def test_rule_engine_matches_known_merchants():
    assert rule_categorize("AMAZON ORDER #123") == "Shopping"
    assert rule_categorize("SWIGGY FOOD DELIVERY") == "Food"
    assert rule_categorize("UBER TRIP") == "Transport"
    assert rule_categorize("NETFLIX SUBSCRIPTION") == "Entertainment"
    assert rule_categorize("MONTHLY SALARY CREDIT") == "Income"


def test_rule_engine_case_insensitive():
    assert rule_categorize("amazon") == "Shopping"
    assert rule_categorize("AmAzOn") == "Shopping"


def test_rule_engine_no_match_returns_none():
    assert rule_categorize("xyzunknownmerchant123") is None


def test_categorize_prefers_rule_over_ml():
    category, source, confidence = categorize("Amazon purchase")
    assert category == "Shopping"
    assert source == "rule"
    assert confidence == 1.0


def test_categorize_ml_fallback_for_unknown_merchant():
    category, source, confidence = categorize("random unclassified merchant xyz")
    assert source == "ml"
    assert 0.0 <= confidence <= 1.0
    assert category in {
        "Shopping", "Food", "Transport", "Bills", "Home", "Recharge",
        "Education", "Health", "Income", "Other", "Entertainment",
    }


def test_categorize_low_confidence_falls_back_to_other():
    # Gibberish should not confidently match a real category
    category, source, confidence = categorize("zzxq flmp qqrs")
    if source == "ml" and confidence < 0.45:
        assert category == "Other"
