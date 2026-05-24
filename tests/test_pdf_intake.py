"""Tests for PDF extraction and upload API."""

from __future__ import annotations

import fitz
import pytest
from fastapi.testclient import TestClient

from backend.services.pdf_extractor import PdfExtractor
from backend.services.text_cleaner import TextCleaner


def _minimal_pdf_bytes(text: str = "Hello world. Sample paragraph for extraction.") -> bytes:
    """Built-in PDF fonts do not embed Persian glyphs; real uploads use document fonts."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


def test_pdf_extractor_returns_pages():
    extractor = PdfExtractor()
    result = extractor.extract(_minimal_pdf_bytes(), filename="test.pdf")
    assert result.page_count == 1
    assert len(result.pages) == 1
    assert result.pages[0].page_number == 1
    assert "Hello" in result.pages[0].text


def test_cleaner_preserves_text_after_extraction():
    extractor = PdfExtractor()
    cleaner = TextCleaner()
    raw = extractor.extract(_minimal_pdf_bytes(), filename="test.pdf")
    cleaned = cleaner.clean_result(raw)
    assert "Hello" in cleaned.full_text


def test_cleaner_handles_persian_unicode():
    cleaner = TextCleaner()
    persian = "سلام.\n\nپاراگراف دوم با   فاصله اضافی."
    cleaned = cleaner.clean(persian)
    assert "سلام" in cleaned
    assert "پاراگراف" in cleaned
    assert "  " not in cleaned


def test_upload_pdf_endpoint(client: TestClient):
    pdf_bytes = _minimal_pdf_bytes()
    response = client.post(
        "/api/v1/pdf/upload",
        files={"file": ("persian-sample.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "persian-sample.pdf"
    assert data["page_count"] == 1
    assert data["intake_id"]
    assert len(data["pages"]) == 1
    assert "Hello" in data["full_text"]


def test_upload_rejects_non_pdf(client: TestClient):
    response = client.post(
        "/api/v1/pdf/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_empty_pdf_fails(client: TestClient):
    response = client.post(
        "/api/v1/pdf/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400
