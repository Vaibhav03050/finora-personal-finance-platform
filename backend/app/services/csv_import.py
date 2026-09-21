"""
CSV ingestion. Bank exports vary a lot in column naming, so we do
best-effort header matching rather than requiring one fixed format.
"""
import io

import pandas as pd
from dateutil import parser as dateparser

from app.services.categorize import categorize

DATE_ALIASES = ["date", "txn date", "transaction date", "value date"]
DESC_ALIASES = ["description", "narration", "particulars", "details", "merchant"]
AMOUNT_ALIASES = ["amount", "amt"]
DEBIT_ALIASES = ["debit", "withdrawal", "withdrawal amt"]
CREDIT_ALIASES = ["credit", "deposit", "deposit amt"]


def _find_column(columns: list[str], aliases: list[str]) -> str | None:
    lower_map = {c.lower().strip(): c for c in columns}
    for alias in aliases:
        if alias in lower_map:
            return lower_map[alias]
    return None


def parse_csv_bytes(content: bytes) -> tuple[list[dict], dict]:
    """Returns (rows, stats). Rows are review-ready dicts, never auto-committed."""
    if not content or not content.strip():
        return [], {"rows_total": 0, "imported": 0, "duplicates": 0, "failed": 0,
                     "error": "This file appears to be empty."}

    try:
        df = pd.read_csv(io.BytesIO(content))
    except pd.errors.EmptyDataError:
        return [], {"rows_total": 0, "imported": 0, "duplicates": 0, "failed": 0,
                     "error": "This file appears to be empty."}
    except pd.errors.ParserError:
        return [], {"rows_total": 0, "imported": 0, "duplicates": 0, "failed": 0,
                     "error": "Couldn't read this as a CSV file. Please check the format."}

    if df.empty:
        return [], {"rows_total": 0, "imported": 0, "duplicates": 0, "failed": 0,
                     "error": "This file has headers but no data rows."}

    df.columns = [str(c).strip() for c in df.columns]
    columns = list(df.columns)

    date_col = _find_column(columns, DATE_ALIASES)
    desc_col = _find_column(columns, DESC_ALIASES)
    amount_col = _find_column(columns, AMOUNT_ALIASES)
    debit_col = _find_column(columns, DEBIT_ALIASES)
    credit_col = _find_column(columns, CREDIT_ALIASES)

    rows_total = len(df)
    parsed, failed = [], 0

    if not date_col or not desc_col or not (amount_col or debit_col or credit_col):
        return [], {"rows_total": rows_total, "imported": 0, "duplicates": 0, "failed": rows_total,
                     "error": "Could not detect date/description/amount columns in this CSV."}

    for _, row in df.iterrows():
        try:
            txn_date = dateparser.parse(str(row[date_col]), dayfirst=True, fuzzy=True).date()
            description_raw = row[desc_col]
            description = "" if pd.isna(description_raw) else str(description_raw).strip()
            if not description:
                description = "Uncategorized transaction"

            if amount_col:
                amt = float(row[amount_col])
                txn_type = "income" if amt >= 0 else "expense"
                amount_rupees = abs(amt)
            else:
                debit_val = float(row[debit_col]) if debit_col and pd.notna(row.get(debit_col)) else 0
                credit_val = float(row[credit_col]) if credit_col and pd.notna(row.get(credit_col)) else 0
                if credit_val > 0:
                    txn_type, amount_rupees = "income", credit_val
                else:
                    txn_type, amount_rupees = "expense", debit_val

            if amount_rupees <= 0:
                failed += 1
                continue

            category, source, confidence = categorize(description)
            if txn_type == "income":
                category = "Income"

            parsed.append({
                "date": txn_date.isoformat(), "merchant": description, "description": description,
                "amount_rupees": amount_rupees, "type": txn_type,
                "category": category, "category_source": source, "confidence": confidence,
                "needs_review": confidence < 0.6,
            })
        except Exception:
            failed += 1
            continue

    stats = {"rows_total": rows_total, "imported": len(parsed), "duplicates": 0, "failed": failed}
    return parsed, stats
