import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import get_current_user
from app.models import User
from app.schemas import ok
from app.services.ocr import OCRUnavailableError, extract_text_from_image, parse_receipt_text, parse_statement_text
from app.services.pdf_import import extract_statement_pdf

logger = logging.getLogger("finora")

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])

# Images are read fully into memory before OCR, so cap size to prevent a
# single large upload from exhausting server memory.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_STATEMENT_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _require_extension(filename: str | None, allowed: set[str], label: str) -> str:
    name = (filename or "").strip()
    suffix = Path(name).suffix.lower()
    if suffix not in allowed:
        expected = ", ".join(sorted(allowed))
        raise HTTPException(status_code=415, detail=f"{label} must use one of these extensions: {expected}.")
    return suffix


def _validate_image_bytes(content: bytes, suffix: str) -> None:
    try:
        from PIL import Image
        from io import BytesIO
        with Image.open(BytesIO(content)) as image:
            image.verify()
    except Exception as exc:
        raise HTTPException(status_code=415, detail=f"The uploaded file is not a valid {suffix[1:].upper()} image.") from exc


@router.post("/statement-photo")
async def upload_statement_photo(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    """Photo of a bank statement / transaction list -> extracted rows for review."""
    suffix = _require_extension(file.filename, ALLOWED_STATEMENT_PHOTO_EXTENSIONS, "Statement photo")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large. Please upload a photo under 10MB.")
    _validate_image_bytes(content, suffix)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        text = extract_text_from_image(tmp_path)
    except OCRUnavailableError as e:
        return ok(
            {"rows": [], "raw_text": ""},
            meta={"status": "ocr_unavailable", "message": str(e), "hint": "You can still enter transactions manually."},
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    rows = parse_statement_text(text)
    status = "parsed" if rows else "no_rows_found"
    return ok({"rows": rows, "raw_text": text[:3000]}, meta={"status": status, "row_count": len(rows)})


@router.post("/statement-pdf")
async def upload_statement_pdf(
    file: UploadFile = File(...),
    password: str | None = Form(default=None),
    user: User = Depends(get_current_user),
):
    """Bank statement PDF -> extracted transaction rows for user review.

    Supports text-based PDFs and scanned/image-only PDFs via Tesseract fallback.
    Nothing is saved until the user confirms the review table.
    """
    _require_extension(file.filename, {".pdf"}, "Bank statement PDF")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File is too large. Please upload a PDF under 20MB.")

    try:
        rows, raw_text, info = extract_statement_pdf(content, file.filename or "statement.pdf", password=password or None)
    except OCRUnavailableError as exc:
        return ok({"rows": [], "raw_text": ""}, meta={"status": "ocr_unavailable", "message": str(exc)})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        # Log the real cause for debugging; the user only ever sees the
        # generic message below. Never include statement content in logs.
        logger.exception("statement-pdf: unhandled error for filename=%r size_bytes=%d", file.filename, len(content))
        raise HTTPException(status_code=400, detail="Couldn't read this PDF. Please upload a valid bank statement PDF.")

    status = "parsed" if rows else "no_rows_found"
    return ok(
        {"rows": rows, "raw_text": raw_text[:3000]},
        meta={"status": status, "row_count": len(rows), **info},
    )


@router.post("/receipt-photo")
async def upload_receipt_photo(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    """Photo of a single receipt -> one candidate expense for confirmation."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large. Please upload a photo under 10MB.")

    suffix = Path(file.filename or "receipt.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        text = extract_text_from_image(tmp_path)
    except OCRUnavailableError as e:
        return ok(None, meta={"status": "ocr_unavailable", "message": str(e)})
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    receipt = parse_receipt_text(text)
    return ok(receipt, meta={"status": "parsed" if receipt.get("amount_rupees") else "needs_manual_entry"})
