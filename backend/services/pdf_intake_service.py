"""Orchestrates PDF extraction, cleaning, and Persian repair (no TTS or chunking)."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.config.settings import Settings
from backend.services.pdf_extractor import PageText, PdfExtractor, PdfExtractionError
from backend.services.persian_text_repair import PersianTextRepairService, RepairResult
from backend.services.text_cleaner import TextCleaner

logger = logging.getLogger(__name__)


@dataclass
class PdfIntakePayload:
    intake_id: str
    filename: str
    page_count: int
    pages: list[dict]
    full_text: str
    preview_text: str
    repair_applied: bool = False
    repair_fix_count: int = 0


class PdfIntakeService:
    """Phase 1: extract → clean → repair → persist for preview / edit."""

    PREVIEW_CHAR_LIMIT = 12_000

    def __init__(
        self,
        settings: Settings,
        extractor: PdfExtractor | None = None,
        cleaner: TextCleaner | None = None,
        repair_service: PersianTextRepairService | None = None,
    ) -> None:
        self._settings = settings
        self._extractor = extractor or PdfExtractor()
        self._cleaner = cleaner or TextCleaner()
        self._repair = repair_service or PersianTextRepairService(
            debug_dir=settings.storage_root / "debug" / "repair",
        )
        self._intake_dir = settings.temp_dir / "intake"
        self._intake_dir.mkdir(parents=True, exist_ok=True)

    def process_upload(self, pdf_bytes: bytes, filename: str) -> PdfIntakePayload:
        safe_name = Path(filename).name or "document.pdf"
        if not safe_name.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are supported.")

        try:
            raw = self._extractor.extract(pdf_bytes, filename=safe_name)
            cleaned = self._cleaner.clean_result(raw)
        except PdfExtractionError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error processing PDF upload: %s", safe_name)
            raise PdfExtractionError(str(exc)) from exc

        if not any(p.text.strip() for p in cleaned.pages):
            logger.warning("PDF contained no extractable text: %s", safe_name)
            raise PdfExtractionError("No text could be extracted from this PDF.")

        intake_id = str(uuid.uuid4())
        before_repair = self._build_full_text(cleaned.pages)
        repaired_pages, repair_result = self._repair_pages(cleaned.pages)

        self._repair.save_diagnostics(intake_id, before_repair, repair_result)
        if repair_result.fix_count:
            logger.info(
                "Persian repair applied: intake=%s fixes=%s",
                intake_id,
                repair_result.fix_count,
            )

        full_text = self._build_full_text(repaired_pages)
        payload = PdfIntakePayload(
            intake_id=intake_id,
            filename=cleaned.filename,
            page_count=cleaned.page_count,
            pages=[
                {"page_number": p.page_number, "text": p.text}
                for p in repaired_pages
            ],
            full_text=full_text,
            preview_text=full_text[: self.PREVIEW_CHAR_LIMIT],
            repair_applied=repair_result.fix_count > 0,
            repair_fix_count=repair_result.fix_count,
        )
        self._save_intake(payload)
        logger.info(
            "PDF intake ready: id=%s file=%s pages=%s",
            intake_id,
            safe_name,
            cleaned.page_count,
        )
        return payload

    def update_text(self, intake_id: str, full_text: str) -> PdfIntakePayload:
        record = self._load_intake(intake_id)
        if record is None:
            raise FileNotFoundError("Intake session not found.")

        record["full_text"] = full_text
        record["preview_text"] = full_text[: self.PREVIEW_CHAR_LIMIT]
        pages = self._split_pages_from_full_text(full_text, record.get("page_count", 1))
        record["pages"] = pages
        self._write_intake_file(intake_id, record)
        return PdfIntakePayload(**record)

    def get_intake(self, intake_id: str) -> PdfIntakePayload | None:
        record = self._load_intake(intake_id)
        if record is None:
            return None
        return PdfIntakePayload(**record)

    def delete_intake(self, intake_id: str) -> None:
        path = self._intake_path(intake_id)
        if path.exists():
            path.unlink()

    def _repair_pages(self, pages: list[PageText]) -> tuple[list[PageText], RepairResult]:
        all_changes = []
        repaired: list[PageText] = []

        for page in pages:
            result = self._repair.repair(page.text)
            repaired.append(PageText(page_number=page.page_number, text=result.text))
            all_changes.extend(result.changes)

        aggregate = RepairResult(
            text=self._build_full_text(repaired),
            changes=all_changes,
        )
        return repaired, aggregate

    @staticmethod
    def _build_full_text(pages: list[PageText]) -> str:
        parts: list[str] = []
        for page in pages:
            body = page.text.strip()
            if body:
                parts.append(f"--- Page {page.page_number} ---\n{body}")
        return "\n\n".join(parts)

    def _split_pages_from_full_text(self, full_text: str, page_count: int) -> list[dict]:
        import re

        pattern = re.compile(r"^--- Page (\d+) ---\s*$", re.MULTILINE)
        parts = pattern.split(full_text)
        if len(parts) > 1:
            pages = []
            i = 1
            while i < len(parts):
                num = int(parts[i])
                body = parts[i + 1].strip() if i + 1 < len(parts) else ""
                pages.append({"page_number": num, "text": body})
                i += 2
            if pages:
                return pages

        return [{"page_number": n, "text": full_text} for n in range(1, page_count + 1)]

    def _save_intake(self, payload: PdfIntakePayload) -> None:
        self._write_intake_file(payload.intake_id, asdict(payload))

    def _write_intake_file(self, intake_id: str, data: dict) -> None:
        path = self._intake_path(intake_id)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_intake(self, intake_id: str) -> dict | None:
        path = self._intake_path(intake_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _intake_path(self, intake_id: str) -> Path:
        return self._intake_dir / f"{intake_id}.json"
