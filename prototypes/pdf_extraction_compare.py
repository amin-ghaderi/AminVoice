"""
Diagnostic: compare Persian PDF text extraction across libraries.

Usage (from project root):
    python prototypes/pdf_extraction_compare.py

Does NOT modify the production PDF pipeline.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# --- Configuration (edit for your test document) ---
PDF_PATH = r"C:\Users\info\Downloads\زمان انتخاب –  رضا  شاه  دوم.pdf"
PAGE_NUMBERS = [4, 5]  # pages to benchmark

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "storage" / "debug" / "pdf_compare"

# Persian / Arabic Unicode ranges
_PERSIAN_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")

# Heuristic thresholds (conservative)
_MIN_PERSIAN_RATIO = 0.08
_ISOLATED_PUNCT_RATIO = 0.12
_SHORT_TOKEN_RATIO = 0.35
_SHORT_TOKEN_MAX_LEN = 2
_BROKEN_LINE_RATIO = 0.25
_DIGIT_FRAGMENT_RATIO = 0.15
_REVERSED_LINE_RATIO = 0.20  # lines starting with terminal punctuation (RTL order bug)


@dataclass
class ExtractionResult:
    method: str
    text: str
    error: str | None = None


@dataclass
class QualityReport:
    length: int
    persian_detected: bool
    persian_char_count: int
    persian_ratio: float
    quality_warning: str
    flags: list[str]


def resolve_pdf_path() -> Path:
    path = Path(PDF_PATH)
    if path.exists():
        return path
    # Fallback: find by partial name in Downloads
    downloads = Path.home() / "Downloads"
    candidates = list(downloads.glob("*.pdf"))
    for candidate in candidates:
        if "شاه" in candidate.name or "انتخاب" in candidate.name:
            return candidate
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(
        f"PDF not found: {PDF_PATH}\n"
        f"Set PDF_PATH at the top of this script to your test file."
    )


def extract_with_pymupdf_text(pdf_path: Path, page_number: int) -> ExtractionResult:
    try:
        import fitz
    except ImportError as exc:
        return ExtractionResult("pymupdf_text", "", str(exc))

    try:
        doc = fitz.open(pdf_path)
        page = doc[page_number - 1]
        text = page.get_text("text") or ""
        doc.close()
        return ExtractionResult("pymupdf_text", text)
    except Exception as exc:
        return ExtractionResult("pymupdf_text", "", str(exc))


def extract_with_pymupdf_blocks(pdf_path: Path, page_number: int) -> ExtractionResult:
    try:
        import fitz
    except ImportError as exc:
        return ExtractionResult("pymupdf_blocks", "", str(exc))

    try:
        doc = fitz.open(pdf_path)
        page = doc[page_number - 1]
        blocks = page.get_text("blocks") or []
        doc.close()
        lines: list[str] = []
        for block in blocks:
            if len(block) >= 5 and block[6] == 0:  # text block
                content = (block[4] or "").strip()
                if content:
                    lines.append(content)
        return ExtractionResult("pymupdf_blocks", "\n\n".join(lines))
    except Exception as exc:
        return ExtractionResult("pymupdf_blocks", "", str(exc))


def extract_with_pdfplumber(pdf_path: Path, page_number: int) -> ExtractionResult:
    try:
        import pdfplumber
    except ImportError as exc:
        return ExtractionResult("pdfplumber", "", str(exc))

    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_number - 1]
            text = page.extract_text() or ""
        return ExtractionResult("pdfplumber", text)
    except Exception as exc:
        return ExtractionResult("pdfplumber", "", str(exc))


def extract_with_pypdf(pdf_path: Path, page_number: int) -> ExtractionResult:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        return ExtractionResult("pypdf", "", str(exc))

    try:
        reader = PdfReader(str(pdf_path))
        page = reader.pages[page_number - 1]
        text = page.extract_text() or ""
        return ExtractionResult("pypdf", text)
    except Exception as exc:
        return ExtractionResult("pypdf", "", str(exc))


def count_persian_chars(text: str) -> int:
    return len(_PERSIAN_RE.findall(text))


def analyze_quality(text: str) -> QualityReport:
    flags: list[str] = []
    stripped = text.strip()
    length = len(stripped)
    persian_count = count_persian_chars(stripped)
    letter_chars = sum(1 for c in stripped if c.isalpha() or _PERSIAN_RE.match(c))
    persian_ratio = persian_count / max(length, 1)
    persian_detected = persian_count >= 20

    if length == 0:
        flags.append("EMPTY_TEXT")
    if not persian_detected and length > 50:
        flags.append("MISSING_PERSIAN")

    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]

    # Reversed RTL extraction (common in pdfplumber on Persian PDFs)
    if lines:
        reversed_lines = sum(
            1 for ln in lines if ln[0] in ".!؟۔,;:" or ln.startswith(")")
        )
        if reversed_lines / len(lines) > _REVERSED_LINE_RATIO:
            flags.append("LIKELY_REVERSED_RTL")
    if "لوا لصف" in stripped or "کيتارکومد" in stripped:
        flags.append("LIKELY_REVERSED_RTL")
    if stripped.count("اس)می") >= 2 or stripped.count(")می") >= 2:
        flags.append("GLYPH_SUBSTITUTION_ARTIFACTS")

    if lines:
        isolated = sum(
            1
            for ln in lines
            if len(ln) <= 3 and not any(_PERSIAN_RE.search(ch) for ch in ln)
        )
        if isolated / len(lines) > _ISOLATED_PUNCT_RATIO:
            flags.append("ISOLATED_PUNCTUATION")

    # Broken line endings: many lines without sentence-ending punctuation
    if lines:
        no_end = sum(
            1
            for ln in lines
            if not re.search(r"[.!?؟۔:\)\]»\"']\s*$", ln)
        )
        if no_end / len(lines) > _BROKEN_LINE_RATIO:
            flags.append("EXCESSIVE_LINE_BREAKS")

    # Abnormal digit fragmentation (single digits on their own lines)
    digit_only_lines = sum(1 for ln in lines if re.fullmatch(r"[\d۰-۹٠-٩\s]+", ln))
    if lines and digit_only_lines / len(lines) > _DIGIT_FRAGMENT_RATIO:
        flags.append("DIGIT_FRAGMENTATION")

    # Very short tokens ratio (broken extraction / missing joins)
    tokens = re.findall(r"[^\s]+", stripped)
    if tokens:
        short = sum(1 for t in tokens if len(t) <= _SHORT_TOKEN_MAX_LEN)
        if short / len(tokens) > _SHORT_TOKEN_RATIO:
            flags.append("SHORT_TOKEN_RATIO_HIGH")

    if persian_detected and persian_ratio < _MIN_PERSIAN_RATIO and length > 200:
        flags.append("LOW_PERSIAN_RATIO")

    # Replacement / mojibake hints
    if "\ufffd" in stripped:
        flags.append("REPLACEMENT_CHARACTERS")

    if persian_count > 50:
        latin_words = len(re.findall(r"[a-zA-Z]{4,}", stripped))
        if latin_words > 8:
            flags.append("MIXED_SCRIPT_FRAGMENTS")

    if any(
        f in flags
        for f in (
            "EMPTY_TEXT",
            "MISSING_PERSIAN",
            "REPLACEMENT_CHARACTERS",
            "SHORT_TOKEN_RATIO_HIGH",
            "LOW_PERSIAN_RATIO",
            "LIKELY_REVERSED_RTL",
            "GLYPH_SUBSTITUTION_ARTIFACTS",
        )
    ):
        warning = "POSSIBLE_BROKEN_TEXT"
    elif flags:
        warning = "MINOR_ISSUES"
    else:
        warning = "OK"

    return QualityReport(
        length=length,
        persian_detected=persian_detected,
        persian_char_count=persian_count,
        persian_ratio=round(persian_ratio, 4),
        quality_warning=warning,
        flags=flags,
    )


def format_blocks_comparison(results: dict[str, ExtractionResult]) -> str:
    labels = {
        "pymupdf_text": "PYMUPDF TEXT",
        "pymupdf_blocks": "PYMUPDF BLOCKS",
        "pdfplumber": "PDFPLUMBER",
        "pypdf": "PYPDF",
    }
    parts: list[str] = []
    for key, label in labels.items():
        result = results[key]
        parts.append("=" * 48)
        parts.append(label)
        parts.append("=" * 48)
        parts.append("")
        if result.error:
            parts.append(f"[ERROR] {result.error}")
        else:
            parts.append(result.text if result.text else "(empty)")
        parts.append("")
    return "\n".join(parts)


def save_results(
    page_number: int,
    results: dict[str, ExtractionResult],
    comparison_text: str,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prefix = f"page_{page_number}"

    file_map = {
        "pymupdf_text": f"{prefix}_pymupdf_text.txt",
        "pymupdf_blocks": f"{prefix}_pymupdf_blocks.txt",
        "pdfplumber": f"{prefix}_pdfplumber.txt",
        "pypdf": f"{prefix}_pypdf.txt",
    }

    for key, filename in file_map.items():
        result = results[key]
        body = result.text if not result.error else f"[ERROR] {result.error}"
        (OUTPUT_DIR / filename).write_text(body, encoding="utf-8")

    (OUTPUT_DIR / f"{prefix}_comparison.txt").write_text(
        comparison_text, encoding="utf-8"
    )


def print_summary(page_number: int, results: dict[str, ExtractionResult]) -> None:
    display_names = {
        "pymupdf_text": "PyMuPDF text",
        "pymupdf_blocks": "PyMuPDF blocks",
        "pdfplumber": "pdfplumber",
        "pypdf": "pypdf",
    }
    print(f"\n--- Page {page_number} ---")
    for key, name in display_names.items():
        result = results[key]
        print(f"\n[{name}]")
        if result.error:
            print(f"  Length: 0")
            print(f"  Persian detected: NO")
            print(f"  Quality warning: ERROR — {result.error}")
            continue
        report = analyze_quality(result.text)
        print(f"  Length: {report.length}")
        print(f"  Persian detected: {'YES' if report.persian_detected else 'NO'}")
        print(f"  Persian chars: {report.persian_char_count} ({report.persian_ratio:.1%} of text)")
        print(f"  Quality warning: {report.quality_warning}")
        if report.flags:
            print(f"  Flags: {', '.join(report.flags)}")


def rank_extractors(results: dict[str, ExtractionResult]) -> list[tuple[str, int]]:
    """Lower score is better."""
    scores: list[tuple[str, int]] = []
    for key, result in results.items():
        if result.error:
            scores.append((key, 10_000))
            continue
        report = analyze_quality(result.text)
        penalty = 0
        if "LIKELY_REVERSED_RTL" in report.flags:
            penalty += 200
        if report.quality_warning == "POSSIBLE_BROKEN_TEXT":
            penalty += 100
        elif report.quality_warning == "MINOR_ISSUES":
            penalty += 20
        penalty += len(report.flags) * 5
        penalty -= min(report.persian_char_count // 10, 50)
        penalty += max(0, 500 - report.length) // 10
        scores.append((key, penalty))
    return sorted(scores, key=lambda x: x[1])


def run_page(pdf_path: Path, page_number: int) -> dict[str, ExtractionResult]:
    extractors = [
        ("pymupdf_text", extract_with_pymupdf_text),
        ("pymupdf_blocks", extract_with_pymupdf_blocks),
        ("pdfplumber", extract_with_pdfplumber),
        ("pypdf", extract_with_pypdf),
    ]
    results: dict[str, ExtractionResult] = {}
    for key, fn in extractors:
        results[key] = fn(pdf_path, page_number)
    comparison = format_blocks_comparison(results)
    save_results(page_number, results, comparison)
    print_summary(page_number, results)
    return results


def _safe_print(message: str) -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("ascii", errors="backslashreplace").decode("ascii"))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    pdf_path = resolve_pdf_path()
    _safe_print(f"PDF: {pdf_path}")
    _safe_print(f"Output: {OUTPUT_DIR}")

    if not PAGE_NUMBERS:
        print("No PAGE_NUMBERS configured.", file=sys.stderr)
        return 1

    all_rankings: dict[int, list[tuple[str, int]]] = {}
    for page_number in PAGE_NUMBERS:
        if page_number < 1:
            print(f"Skipping invalid page: {page_number}")
            continue
        results = run_page(pdf_path, page_number)
        all_rankings[page_number] = rank_extractors(results)

    print("\n" + "=" * 48)
    print("RANKING (best first, heuristic)")
    print("=" * 48)
    labels = {
        "pymupdf_text": "PyMuPDF text",
        "pymupdf_blocks": "PyMuPDF blocks",
        "pdfplumber": "pdfplumber",
        "pypdf": "pypdf",
    }
    for page_number, ranking in all_rankings.items():
        ordered = [labels[k] for k, _ in ranking]
        print(f"  Page {page_number}: {' > '.join(ordered)}")

    print(f"\nFiles written to: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
