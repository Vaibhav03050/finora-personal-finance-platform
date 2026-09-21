import hashlib
from datetime import date

from app.services.categorize import normalize_text


def compute_dedupe_hash(user_id: int, txn_date: date, amount_minor: int, merchant: str) -> str:
    normalized_merchant = normalize_text(merchant or "")
    raw = f"{user_id}|{txn_date.isoformat()}|{amount_minor}|{normalized_merchant}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
