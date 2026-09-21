from pathlib import Path

import pytest

from app.routers.uploads import _require_extension, _validate_image_bytes


def test_pdf_extension_rejects_non_pdf():
    with pytest.raises(Exception) as exc:
        _require_extension("statement.txt", {".pdf"}, "Bank statement PDF")
    assert getattr(exc.value, "status_code", None) == 415


def test_statement_photo_extension_rejects_pdf():
    with pytest.raises(Exception) as exc:
        _require_extension("statement.pdf", {".jpg", ".jpeg", ".png", ".webp"}, "Statement photo")
    assert getattr(exc.value, "status_code", None) == 415


def test_csv_extension_rejects_xlsx():
    with pytest.raises(Exception) as exc:
        _require_extension("transactions.xlsx", {".csv"}, "CSV bank export")
    assert getattr(exc.value, "status_code", None) == 415


def test_statement_photo_ocr_extracts_transactions():
    pytest.importorskip("PIL")
    pytest.importorskip("pytesseract")
    from PIL import Image, ImageDraw, ImageFont
    import pytesseract
    from app.services.ocr import extract_text_from_image, parse_statement_text

    try:
        pytesseract.get_tesseract_version()
    except Exception:
        pytest.skip("Tesseract is not installed in this test environment")

    image = Image.new("RGB", (1400, 500), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42)
    except Exception:
        font = None
    lines = [
        "DATE MERCHANT AMOUNT",
        "12/08/2026 UPI-AMAZON -1299.00",
        "13/08/2026 SALARY +52000.00",
        "14/08/2026 UBER -320.00",
    ]
    for i, line in enumerate(lines):
        draw.text((40, 40 + i * 100), line, fill="black", font=font)

    path = Path("/tmp/finora_statement_photo_test.png")
    image.save(path)
    try:
        text = extract_text_from_image(str(path))
        rows = parse_statement_text(text)
    finally:
        path.unlink(missing_ok=True)

    assert len(rows) >= 2
    assert any(r["merchant"] == "UPI-AMAZON" and r["type"] == "expense" for r in rows)
    assert any(r["merchant"] == "SALARY" and r["type"] == "income" for r in rows)
