"""Financial transaction endpoints: manual entry, natural-language parsing,
CRUD, CSV upload, bulk-confirm (used by both CSV and OCR review flows), and
the privacy "delete all my data" control."""
from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlmodel import Session, select

from app.auth import get_current_user
from app.database import get_session
from app.models import AuditLog, Transaction, User
from app.schemas import NaturalLanguageEntry, TransactionCreate, TransactionUpdate, fail, ok
from app.services.categorize import categorize
from app.services.csv_import import parse_csv_bytes
from app.services.dedupe import compute_dedupe_hash
from app.services.money import to_major, to_minor
from app.services.nl_parser import parse_entry

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])

# Uploads are read fully into memory, so cap size to prevent a single large
# file from exhausting server memory. 10MB comfortably covers any real bank
# CSV export.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _to_out(t: Transaction) -> dict:
    return {
        "id": t.id, "date": t.txn_date.isoformat(), "merchant": t.merchant, "description": t.description,
        "amount_rupees": to_major(t.amount_minor), "currency": t.currency,
        "type": t.txn_type.value if hasattr(t.txn_type, "value") else t.txn_type,
        "category": t.category, "category_source": t.category_source.value if hasattr(t.category_source, "value") else t.category_source,
        "confidence": t.confidence, "source": t.source.value if hasattr(t.source, "value") else t.source,
        "needs_review": t.needs_review,
    }


@router.get("")
def list_transactions(
    category: Optional[str] = None,
    type: Optional[str] = None,
    date_from: Optional[date_type] = None,
    date_to: Optional[date_type] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    query = select(Transaction).where(Transaction.user_id == user.id)
    if category:
        query = query.where(Transaction.category == category)
    if type:
        query = query.where(Transaction.txn_type == type)
    if date_from:
        query = query.where(Transaction.txn_date >= date_from)
    if date_to:
        query = query.where(Transaction.txn_date <= date_to)

    all_rows = session.exec(query).all()
    if search:
        s = search.lower()
        all_rows = [t for t in all_rows if s in t.merchant.lower() or s in t.description.lower()]

    all_rows.sort(key=lambda t: t.txn_date, reverse=True)
    total = len(all_rows)
    start = (page - 1) * page_size
    page_rows = all_rows[start:start + page_size]

    return ok(
        [_to_out(t) for t in page_rows],
        meta={"page": page, "page_size": page_size, "total": total},
    )


@router.post("")
def create_transaction(payload: TransactionCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if payload.type not in ("income", "expense"):
        raise HTTPException(status_code=400, detail="type must be 'income' or 'expense'")

    amount_minor = to_minor(payload.amount_rupees)
    if payload.category:
        category, source, confidence = payload.category, "manual", 1.0
    else:
        category, source, confidence = categorize(f"{payload.merchant} {payload.description}".strip())
        if payload.type == "income" and category != "Income":
            category = "Income"

    dedupe_hash = compute_dedupe_hash(user.id, payload.date, amount_minor, payload.merchant or payload.description)

    existing = session.exec(select(Transaction).where(
        Transaction.user_id == user.id, Transaction.dedupe_hash == dedupe_hash
    )).first()
    if existing:
        return ok(_to_out(existing), meta={"duplicate": True})

    txn = Transaction(
        user_id=user.id, txn_date=payload.date, merchant=payload.merchant, description=payload.description,
        amount_minor=amount_minor, txn_type=payload.type, category=category, category_source=source,
        confidence=confidence, source="manual", dedupe_hash=dedupe_hash,
    )
    session.add(txn)
    session.commit()
    session.refresh(txn)
    return ok(_to_out(txn))


@router.post("/parse-natural-language")
def parse_natural_language(payload: NaturalLanguageEntry, user: User = Depends(get_current_user)):
    """Parses text like 'Spent 250 on lunch' into a draft transaction for confirmation. Nothing is saved yet."""
    parsed = parse_entry(payload.text)
    if not parsed:
        return ok(None, meta={"parsed": False, "message": "Couldn't find an amount in that text. Try including a number, e.g. 'Spent 250 on lunch'."})
    return ok(parsed, meta={"parsed": True})


@router.put("/{txn_id}")
def update_transaction(txn_id: int, payload: TransactionUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    txn = session.get(Transaction, txn_id)
    if not txn or txn.user_id != user.id:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if payload.date is not None:
        txn.txn_date = payload.date
    if payload.merchant is not None:
        txn.merchant = payload.merchant
    if payload.description is not None:
        txn.description = payload.description
    if payload.amount_rupees is not None:
        txn.amount_minor = to_minor(payload.amount_rupees)
    if payload.type is not None:
        txn.txn_type = payload.type
    if payload.category is not None:
        txn.category = payload.category
        txn.category_source = "manual"
        txn.confidence = 1.0
    txn.needs_review = False
    txn.dedupe_hash = compute_dedupe_hash(user.id, txn.txn_date, txn.amount_minor, txn.merchant)

    session.add(txn)
    session.commit()
    session.refresh(txn)
    return ok(_to_out(txn))


@router.delete("/{txn_id}")
def delete_transaction(txn_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    txn = session.get(Transaction, txn_id)
    if not txn or txn.user_id != user.id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    session.delete(txn)
    session.commit()
    return ok({"deleted": True})


@router.post("/bulk-confirm")
def bulk_confirm(rows: list[dict], user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """Commits a batch of reviewed/edited rows (from OCR or CSV) into the ledger, deduping as it goes."""
    imported, duplicates, failed = 0, 0, 0
    for row in rows:
        try:
            txn_date = date_type.fromisoformat(row["date"])
            amount_minor = to_minor(float(row["amount_rupees"]))
            merchant = row.get("merchant") or row.get("description", "")
            dedupe_hash = compute_dedupe_hash(user.id, txn_date, amount_minor, merchant)

            existing = session.exec(select(Transaction).where(
                Transaction.user_id == user.id, Transaction.dedupe_hash == dedupe_hash
            )).first()
            if existing:
                duplicates += 1
                continue

            txn = Transaction(
                user_id=user.id, txn_date=txn_date, merchant=merchant, description=row.get("description", merchant),
                amount_minor=amount_minor, txn_type=row["type"], category=row.get("category", "Other"),
                category_source=row.get("category_source", "manual"), confidence=row.get("confidence", 1.0),
                source=row.get("source", "manual"), dedupe_hash=dedupe_hash, needs_review=False,
            )
            session.add(txn)
            imported += 1
        except Exception:
            failed += 1
            continue

    session.commit()
    session.add(AuditLog(user_id=user.id, action="bulk_confirm", detail=f"imported={imported} dup={duplicates} failed={failed}"))
    session.commit()
    return ok({"imported": imported, "duplicates": duplicates, "failed": failed})


@router.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    filename = (file.filename or "").strip().lower()
    if not filename.endswith(".csv"):
        raise HTTPException(status_code=415, detail="CSV bank export must use the .csv extension.")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large. Please upload a file under 10MB.")
    try:
        rows, stats = parse_csv_bytes(content)
    except Exception as e:
        return ok({"rows": [], "stats": {"rows_total": 0, "imported": 0, "duplicates": 0, "failed": 0,
                                          "error": "Couldn't read this file. Please check it's a valid CSV."}})
    return ok({"rows": rows, "stats": stats})


@router.delete("/data/all")
def delete_all_my_data(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """Privacy control: permanently deletes all of this user's transactions."""
    txns = session.exec(select(Transaction).where(Transaction.user_id == user.id)).all()
    for t in txns:
        session.delete(t)
    session.commit()
    session.add(AuditLog(user_id=user.id, action="delete_all_transactions", detail=f"count={len(txns)}"))
    session.commit()
    return ok({"deleted": len(txns)})
