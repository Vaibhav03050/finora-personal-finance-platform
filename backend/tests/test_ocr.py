"""Tests for statement/receipt text parsing (post-OCR). We test the parsing
logic directly with representative OCR'd text rather than re-running the
OCR engine itself, since that would make tests depend on Tesseract's exact
character-level output."""
from app.services.ocr import parse_receipt_text, parse_statement_text


def test_parse_statement_matches_spec_worked_example():
    text = "12/08/26 AMAZON -1299\n13/08/26 UBER -320\n14/08/26 SALARY +52000"
    rows = parse_statement_text(text)
    assert len(rows) == 3
    assert rows[0]["merchant"] == "AMAZON"
    assert rows[0]["amount_rupees"] == 1299.0
    assert rows[0]["type"] == "expense"
    assert rows[0]["category"] == "Shopping"
    assert rows[2]["type"] == "income"
    assert rows[2]["category"] == "Income"


def test_parse_statement_all_rows_flagged_for_review():
    text = "12/08/26 AMAZON -1299"
    rows = parse_statement_text(text)
    assert all(r["needs_review"] for r in rows)
    assert all(r["confidence"] < 1.0 for r in rows)  # never full-confidence, always reviewable


def test_parse_statement_handles_missing_whitespace_before_amount():
    text = "12/08/26 AMAZON-1299"
    rows = parse_statement_text(text)
    assert len(rows) == 1
    assert rows[0]["merchant"] == "AMAZON"
    assert rows[0]["amount_rupees"] == 1299.0


def test_parse_statement_ignores_unparseable_lines():
    text = "this is not a transaction line\nneither is this"
    rows = parse_statement_text(text)
    assert rows == []


def test_parse_statement_empty_text_returns_empty_list():
    assert parse_statement_text("") == []


def test_parse_receipt_extracts_merchant_date_total():
    text = "CAFE XYZ RESTAURANT\nDate: 10/08/2026\nItem 1 250\nItem 2 450\nTotal: 1240"
    receipt = parse_receipt_text(text)
    assert receipt["merchant"] == "CAFE XYZ RESTAURANT"
    assert receipt["date"] == "2026-08-10"
    assert receipt["amount_rupees"] == 1240.0
    assert receipt["category"] == "Food"
    assert receipt["needs_review"] is True


def test_parse_receipt_no_total_line_returns_none_amount():
    text = "SOME SHOP\nrandom text with no total keyword"
    receipt = parse_receipt_text(text)
    assert receipt["amount_rupees"] is None
    assert receipt["confidence"] == 0.0
