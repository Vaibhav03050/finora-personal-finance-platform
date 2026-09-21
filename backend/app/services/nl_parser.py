"""
Deterministic parsing of short natural-language transaction entries like
"Spent 250 on lunch" or "Received 52000 salary". Amounts are extracted with
regex, never guessed/invented by an LLM - this keeps the app usable and
trustworthy with zero AI dependency.
"""
import re
from datetime import date

from app.services.categorize import categorize

INCOME_KEYWORDS = ["received", "got", "earned", "salary", "credited", "income", "refund"]
EXPENSE_KEYWORDS = ["spent", "paid", "bought", "purchase", "debited"]

AMOUNT_PATTERN = re.compile(r"(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)


def parse_entry(text: str) -> dict | None:
    text_clean = text.strip()
    if not text_clean:
        return None

    match = AMOUNT_PATTERN.search(text_clean)
    if not match:
        return None
    amount_str = match.group(1).replace(",", "")
    try:
        amount_rupees = float(amount_str)
    except ValueError:
        return None
    if amount_rupees <= 0:
        return None

    lower = text_clean.lower()
    txn_type = "expense"
    for kw in INCOME_KEYWORDS:
        if kw in lower:
            txn_type = "income"
            break

    # description = text with the amount token stripped out
    description = AMOUNT_PATTERN.sub("", text_clean).strip(" .,-")
    description = re.sub(r"\s+", " ", description) or text_clean

    category, source, confidence = categorize(description)
    if txn_type == "income" and category != "Income":
        category = "Income"

    return {
        "amount_rupees": amount_rupees,
        "type": txn_type,
        "category": category,
        "category_source": source,
        "confidence": confidence,
        "description": description,
        "date": date.today().isoformat(),
    }
