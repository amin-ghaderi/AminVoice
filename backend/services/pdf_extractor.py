"""PDF text extraction — preserves page structure for Persian documents."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


@dataclass(frozen=True)
class PdfExtractionResult:
    filename: str
    page_count: int
    pages: list[PageText]

    @property
    def full_text(self) -> str:
        """Pages joined with clear separators for preview and downstream chunking."""
        if not self.pages:
            return ""
        parts: list[str] = []
        for page in self.pages:
            body = page.text.strip()
            if body:
                parts.append(f"--- Page {page.page_number} ---\n{body}")
        return "\n\n".join(parts)


class PdfExtractor:
    """Extracts plain text from PDF bytes, one section per page."""

    def extract(self, pdf_bytes: bytes, filename: str = "document.pdf") -> PdfExtractionResult:
        if not pdf_bytes:
            raise ValueError("PDF file is empty.")

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            logger.exception("Failed to open PDF: %s", filename)
            raise PdfExtractionError(f"Could not read PDF: {exc}") from exc

        try:
            pages: list[PageText] = []
            for index in range(len(doc)):
                page = doc[index]
                # "text" mode keeps line breaks and reading order (works well for Persian).
                raw = page.get_text("text") or ""
                pages.append(PageText(page_number=index + 1, text=raw))
            return PdfExtractionResult(
                filename=filename,
                page_count=len(doc),
                pages=pages,
            )
        except Exception as exc:
            logger.exception("Failed to extract text from PDF: %s", filename)
            raise PdfExtractionError(f"Text extraction failed: {exc}") from exc
        finally:
            doc.close()


class PdfExtractionError(Exception):
    """Raised when PDF parsing or text extraction fails."""
