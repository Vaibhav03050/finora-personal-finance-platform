from pathlib import Path


def test_upload_ui_has_pdf_and_statement_photo_but_no_receipt_option():
    js = (Path(__file__).parents[2] / "frontend" / "static" / "js" / "pages.js").read_text(encoding="utf-8")
    start = js.index("function uploadZonesHtml")
    end = js.index("function attachUploadHandlers", start)
    upload_ui = js[start:end]
    assert "Bank statement PDF" in upload_ui
    assert "Photo of a statement" in upload_ui
    assert "Photo of a receipt" not in upload_ui
    assert 'accept="application/pdf,.pdf"' in upload_ui


def test_pdf_scanned_mode_label_matches_backend():
    js = (Path(__file__).parents[2] / "frontend" / "static" / "js" / "pages.js").read_text(encoding="utf-8")
    assert 'extraction_mode === "ocr_fallback"' in js
