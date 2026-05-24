"""Conservative text normalization for TTS-ready Persian prose."""

from __future__ import annotations

import re

from backend.services.pdf_extractor import PageText, PdfExtractionResult

# Zero-width and BOM characters that often appear in PDF extraction.
_INVISIBLE_CHARS = re.compile(
    r"[\u200c\u200d\u200e\u200f\u202a-\u202e\u2060\ufeff]"
)

# Collapse runs of spaces/tabs on the same line (not newlines).
_INLINE_SPACE = re.compile(r"[^\S\n]+")

# More than two consecutive newlines → paragraph break (two).
_EXTRA_BLANK_LINES = re.compile(r"\n{3,}")

# Hyphen or soft hyphen at end of line followed by continuation (Latin PDFs).
_LATIN_LINE_BREAK_HYPHEN = re.compile(r"(\w)-\n(\w)", re.UNICODE)


class TextCleaner:
    """Applies light cleaning; preserves paragraphs and punctuation."""

    def clean(self, text: str) -> str:
        if not text:
            return ""

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = _INVISIBLE_CHARS.sub("", text)
        text = _LATIN_LINE_BREAK_HYPHEN.sub(r"\1\2", text)
        text = self._join_soft_wrapped_lines(text)
        text = _INLINE_SPACE.sub(" ", text)
        text = _EXTRA_BLANK_LINES.sub("\n\n", text)

        # Trim trailing spaces per line without removing intentional blank lines.
        lines = [line.rstrip() for line in text.split("\n")]
        return "\n".join(lines).strip()

    def clean_pages(self, pages: list[PageText]) -> list[PageText]:
        return [
            PageText(page_number=page.page_number, text=self.clean(page.text))
            for page in pages
        ]

    def clean_result(self, result: PdfExtractionResult) -> PdfExtractionResult:
        cleaned_pages = self.clean_pages(result.pages)
        return PdfExtractionResult(
            filename=result.filename,
            page_count=result.page_count,
            pages=cleaned_pages,
        )

    def _join_soft_wrapped_lines(self, text: str) -> str:
        """
        Join lines that look like mid-paragraph wraps (conservative).

        Keeps blank lines and lines that end with sentence punctuation.
        """
        lines = text.split("\n")
        if len(lines) <= 1:
            return text

        sentence_end = re.compile(r"[.!?؟۔:\]\)»\"']\s*$")
        merged: list[str] = []
        buffer = ""

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if buffer:
                    merged.append(buffer)
                    buffer = ""
                merged.append("")
                continue

            if not buffer:
                buffer = stripped
                continue

            if sentence_end.search(buffer) or stripped.startswith(("-", "•", "*", "#")):
                merged.append(buffer)
                buffer = stripped
            else:
                buffer = f"{buffer} {stripped}"

        if buffer:
            merged.append(buffer)

        return "\n".join(merged)
