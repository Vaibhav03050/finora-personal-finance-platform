from app.services.ocr import parse_statement_text


def test_parse_common_bank_pdf_row_with_debit_marker():
    rows = parse_statement_text("12/08/2026 UPI-AMAZON DR 1,299.00 48,701.00")
    assert len(rows) == 1
    assert rows[0]["merchant"] == "UPI-AMAZON"
    assert rows[0]["amount_rupees"] == 1299.0
    assert rows[0]["type"] == "expense"
    assert rows[0]["needs_review"] is True


def test_parse_common_bank_pdf_row_with_credit_marker():
    rows = parse_statement_text("13/08/2026 SALARY CR 52,000.00 100,701.00")
    assert len(rows) == 1
    assert rows[0]["amount_rupees"] == 52000.0
    assert rows[0]["type"] == "income"
    assert rows[0]["category"] == "Income"


def test_pdf_style_rows_are_low_confidence_when_columns_are_ambiguous():
    rows = parse_statement_text("14/08/2026 POS STORE 850.00 99,851.00")
    assert len(rows) == 1
    assert rows[0]["amount_rupees"] == 850.0
    assert rows[0]["confidence"] <= 0.70


def test_canara_classic_statement_row_maps_withdraw_and_deposit_columns():
    text = (
        "TRANS DATE VALUE DATE BRANCH REF/CHQ.NO DESCRIPTION WITHDRAWS DEPOSIT BALANCE\n"
        "18-SEP-22 18-SEP-22 4941 DEBIT CARD ANNUAL CHARGES 148.00 0.00 57,852.27\n"
        "28-SEP-22 28-SEP-22 33 208758036562 UPI/CR/208723639645/ARVAJ/PYTM/**02340@YBL/PAYMENT 0.00 10,891.48 70,400.27"
    )
    rows = parse_statement_text(text)
    assert len(rows) == 2
    assert rows[0]["amount_rupees"] == 148.0
    assert rows[0]["type"] == "expense"
    assert rows[1]["amount_rupees"] == 10891.48
    assert rows[1]["type"] == "income"


def test_canara_cams_statement_uses_debit_credit_marker_before_amount():
    text = (
        "//AXL73b22 09/09/2024 10:59:16 UPI/DR/461994908429/ROJA "
        "MK/SBIN/**k1234@ibl/Payment 2024-09-09T00:00:00 09/09/2024 "
        "10:59:16 nt 400647604973 OTHERS DEBIT 2500.00 801.62 353748"
    )
    rows = parse_statement_text(text)
    assert len(rows) == 1
    assert rows[0]["amount_rupees"] == 2500.0
    assert rows[0]["type"] == "expense"


def test_sbi_style_debit_credit_balance_row():
    text = (
        "Txn Date Value Date Description Ref No./Cheque No Debit Credit Balance\n"
        "01/08/2026 01/08/2026 UPI/AMAZON/12345 1,299.00 0.00 48,701.00\n"
        "02/08/2026 02/08/2026 SALARY/ACME 0.00 52,000.00 100,701.00"
    )
    rows = parse_statement_text(text)
    assert len(rows) == 2
    assert rows[0]["amount_rupees"] == 1299.0 and rows[0]["type"] == "expense"
    assert rows[1]["amount_rupees"] == 52000.0 and rows[1]["type"] == "income"


def test_hdfc_style_withdrawal_deposit_closing_balance():
    text = (
        "Date Narration Chq/Ref No Value Date Withdrawal Amt Deposit Amt Closing Balance\n"
        "05/08/2026 UPI-FOOD-998877 05/08/2026 850.00 0.00 49,851.00\n"
        "06/08/2026 NEFT-SALARY-ABC 06/08/2026 0.00 50,000.00 99,851.00"
    )
    rows = parse_statement_text(text)
    assert len(rows) == 2
    assert rows[0]["amount_rupees"] == 850.0 and rows[0]["type"] == "expense"
    assert rows[1]["amount_rupees"] == 50000.0 and rows[1]["type"] == "income"


def test_icici_axis_style_amount_balance_with_explicit_dr_cr():
    text = (
        "Transaction Date Transaction Remarks Withdrawal Amount Deposit Amount Balance\n"
        "07/08/2026 UPI/DR/123456/SHOP 2,450.00 0.00 47,401.00\n"
        "08/08/2026 UPI/CR/987654/REFUND 0.00 750.00 48,151.00"
    )
    rows = parse_statement_text(text)
    assert len(rows) == 2
    assert rows[0]["amount_rupees"] == 2450.0 and rows[0]["type"] == "expense"
    assert rows[1]["amount_rupees"] == 750.0 and rows[1]["type"] == "income"


def test_bank_row_does_not_treat_utr_as_transaction_amount():
    text = "10/08/2026 UTR 987654321012345678 UPI/SHOP 1,250.00 20,000.00"
    rows = parse_statement_text(text)
    assert len(rows) == 1
    assert rows[0]["amount_rupees"] == 1250.0


def test_iso_date_bank_statement_row():
    text = "2026-08-11 IMPS/CR/SALARY 25,000.00 75,000.00"
    rows = parse_statement_text(text)
    assert len(rows) == 1
    assert rows[0]["amount_rupees"] == 25000.0
    assert rows[0]["type"] == "income"
