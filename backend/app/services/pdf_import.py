"""Bank-statement PDF extraction with text and scanned-PDF fallback.

PDF imports are intentionally best-effort: extracted transactions are returned
as editable review candidates and are never written to the ledger automatically.
"""
import logging
from pathlib import Path

from app.services.ocr import OCRUnavailableError, extract_text_from_image, parse_statement_text

logger = logging.getLogger("finora")

MAX_PDF_PAGES = 25
MAX_EXTRACTED_TEXT = 500_000


def extract_statement_pdf(content: bytes, filename: str = "statement.pdf", password: str | None = None) -> tuple[list[dict], str, dict]:
    # Diagnostic logging here is intentionally limited to structural/metadata
    # facts (file name, size, page count, extraction method, counts). Never
    # log extracted narration text, account numbers or balances.
    logger.info("statement-pdf: received filename=%r size_bytes=%d", filename, len(content))

    if not content.startswith(b"%PDF"):
        logger.warning("statement-pdf: rejected filename=%r reason=not_a_pdf_signature", filename)
        raise ValueError("This file does not appear to be a valid PDF.")

    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        logger.error("statement-pdf: PyMuPDF not installed: %s", exc)
        raise OCRUnavailableError(f"PDF support is not installed: {exc}") from exc

    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        logger.warning("statement-pdf: failed to open filename=%r error=%s", filename, exc)
        raise ValueError("Couldn't open this PDF. Please upload a valid bank statement PDF.") from exc

    try:
        if document.needs_pass:
            if not password:
                raise ValueError("This PDF is password-protected. Enter the PDF password and upload it again. Canara Bank statements commonly use the last 8 digits of the account number as the PDF password.")
            if not document.authenticate(password):
                raise ValueError("The PDF password is incorrect. Please check the password and try again.")
        page_count = len(document)
        if page_count == 0:
            raise ValueError("The PDF has no pages.")
        if page_count > MAX_PDF_PAGES:
            logger.warning("statement-pdf: rejected filename=%r reason=too_many_pages pages=%d", filename, page_count)
            raise ValueError(f"This PDF has {page_count} pages. Please upload a statement with {MAX_PDF_PAGES} pages or fewer.")

        text_parts = []
        pages_with_text = 0
        for page in document:
            text = page.get_text("text") or ""
            if text.strip():
                pages_with_text += 1
            text_parts.append(text)

        raw_text = "\n".join(text_parts)[:MAX_EXTRACTED_TEXT]
        try:
            rows = parse_statement_text(raw_text)
        except Exception:
            # A parsing bug (e.g. a downstream categorization error) should
            # not be reported to the user as an unreadable PDF. Log the real
            # cause and continue as if no rows were found, so the OCR
            # fallback and/or the "no rows found" path can still run/return.
            logger.exception(
                "statement-pdf: text parsing raised for filename=%r (pages=%d, text_len=%d)",
                filename, page_count, len(raw_text),
            )
            rows = []

        logger.info(
            "statement-pdf: text-layer extraction filename=%r pages=%d pages_with_text=%d text_len=%d rows=%d",
            filename, page_count, pages_with_text, len(raw_text), len(rows),
        )

        # Scanned/image-only PDFs have little or no selectable text. Render
        # those pages and send them through the existing Tesseract OCR path.
        if not rows:
            ocr_parts = []
            ocr_failed = False
            for page in document:
                pix = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
                image_path = Path(f"/tmp/finora_statement_{page.number}.png")
                pix.save(str(image_path))
                try:
                    ocr_parts.append(extract_text_from_image(str(image_path)))
                except OCRUnavailableError:
                    ocr_failed = True
                    raise
                finally:
                    image_path.unlink(missing_ok=True)
            ocr_text = "\n".join(ocr_parts)[:MAX_EXTRACTED_TEXT]
            try:
                ocr_rows = parse_statement_text(ocr_text)
            except Exception:
                logger.exception(
                    "statement-pdf: OCR-text parsing raised for filename=%r (pages=%d, text_len=%d)",
                    filename, page_count, len(ocr_text),
                )
                ocr_rows = []

            logger.info(
                "statement-pdf: OCR fallback filename=%r pages=%d text_len=%d rows=%d ocr_failed=%s",
                filename, page_count, len(ocr_text), len(ocr_rows), ocr_failed,
            )

            # Prefer OCR results only when they actually found something;
            # otherwise keep the original (possibly empty) text-layer result
            # so raw_text still reflects what selectable text existed.
            if ocr_rows:
                raw_text, rows, extraction_mode = ocr_text, ocr_rows, "ocr_fallback"
            elif ocr_text.strip() and not raw_text.strip():
                raw_text, extraction_mode = ocr_text, "ocr_fallback_no_rows"
            else:
                extraction_mode = "pdf_text_no_rows"
        else:
            extraction_mode = "pdf_text"

        logger.info(
            "statement-pdf: done filename=%r extraction_mode=%s final_row_count=%d",
            filename, extraction_mode, len(rows),
        )

        return rows, raw_text, {
            "page_count": page_count,
            "pages_with_text": pages_with_text,
            "extraction_mode": extraction_mode,
        }
    finally:
        document.close()
