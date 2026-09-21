"""Tests for CSV ingestion covering varied bank export formats and malformed data."""
from app.services.csv_import import parse_csv_bytes


def test_standard_single_amount_column():
    csv = b"Date,Description,Amount\n01/07/2026,Amazon Purchase,-1500\n02/07/2026,Salary Credit,52000\n"
    rows, stats = parse_csv_bytes(csv)
    assert stats["imported"] == 2
    assert rows[0]["type"] == "expense"
    assert rows[0]["amount_rupees"] == 1500.0
    assert rows[1]["type"] == "income"
    assert rows[1]["category"] == "Income"


def test_debit_credit_column_format():
    csv = (
        b"Txn Date,Narration,Withdrawal Amt,Deposit Amt\n"
        b"01/07/2026,UBER TRIP,320,\n"
        b"02/07/2026,SALARY,,52000\n"
    )
    rows, stats = parse_csv_bytes(csv)
    assert stats["imported"] == 2
    assert rows[0]["type"] == "expense"
    assert rows[0]["amount_rupees"] == 320.0
    assert rows[1]["type"] == "income"
    assert rows[1]["amount_rupees"] == 52000.0


def test_blank_description_does_not_become_literal_nan_string():
    csv = b"Date,Description,Amount\n04/07/2026,,-300\n"
    rows, stats = parse_csv_bytes(csv)
    assert stats["imported"] == 1
    assert rows[0]["description"] != "nan"
    assert rows[0]["merchant"] != "nan"
    assert rows[0]["description"] == "Uncategorized transaction"


def test_malformed_rows_are_skipped_not_crashed():
    csv = (
        b"Date,Description,Amount\n"
        b"01/07/2026,Good Row,-100\n"
        b",Missing Date,-200\n"
        b"03/07/2026,Non Numeric,abc\n"
        b"05/07/2026,Zero Amount,0\n"
        b"06/07/2026,Valid Row 2,-750\n"
    )
    rows, stats = parse_csv_bytes(csv)
    assert stats["rows_total"] == 5
    assert stats["imported"] == 2  # Good Row + Valid Row 2
    assert stats["failed"] == 3    # missing date, non-numeric, zero amount


def test_unrecognized_headers_fails_gracefully_no_crash():
    csv = b"Foo,Bar,Baz\n1,2,3\n"
    rows, stats = parse_csv_bytes(csv)
    assert rows == []
    assert stats["imported"] == 0
    assert "error" in stats


def test_empty_csv_does_not_crash():
    csv = b"Date,Description,Amount\n"
    rows, stats = parse_csv_bytes(csv)
    assert rows == []
    assert stats["rows_total"] == 0
