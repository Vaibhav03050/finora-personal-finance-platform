import sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.dedupe import compute_dedupe_hash
from app.services.nl_parser import parse_entry


def test_dedupe_hash_identical_inputs_match():
    h1 = compute_dedupe_hash(1, date(2026, 1, 1), 10000, "Amazon")
    h2 = compute_dedupe_hash(1, date(2026, 1, 1), 10000, "Amazon")
    assert h1 == h2


def test_dedupe_hash_case_insensitive_merchant():
    h1 = compute_dedupe_hash(1, date(2026, 1, 1), 10000, "AMAZON")
    h2 = compute_dedupe_hash(1, date(2026, 1, 1), 10000, "amazon")
    assert h1 == h2


def test_dedupe_hash_different_amount_differs():
    h1 = compute_dedupe_hash(1, date(2026, 1, 1), 10000, "Amazon")
    h2 = compute_dedupe_hash(1, date(2026, 1, 1), 10001, "Amazon")
    assert h1 != h2


def test_dedupe_hash_different_user_differs():
    h1 = compute_dedupe_hash(1, date(2026, 1, 1), 10000, "Amazon")
    h2 = compute_dedupe_hash(2, date(2026, 1, 1), 10000, "Amazon")
    assert h1 != h2


def test_nl_parser_expense():
    result = parse_entry("Spent 250 on lunch")
    assert result["amount_rupees"] == 250.0
    assert result["type"] == "expense"


def test_nl_parser_income():
    result = parse_entry("Received 52000 salary")
    assert result["amount_rupees"] == 52000.0
    assert result["type"] == "income"
    assert result["category"] == "Income"


def test_nl_parser_with_currency_symbol():
    result = parse_entry("Paid ₹1,299 for shoes")
    assert result["amount_rupees"] == 1299.0


def test_nl_parser_no_amount_returns_none():
    assert parse_entry("I went to the market today") is None


def test_nl_parser_empty_string_returns_none():
    assert parse_entry("") is None


def test_nl_parser_never_invents_amount_not_present():
    # Confirms the parser only extracts, never fabricates, a number.
    result = parse_entry("bought groceries")
    assert result is None
