"""Chunk preview using the same splitter as TTS generation."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.services.text_splitter import (
    SOFT_MAX_CHARS,
    VALIDATION_MAX_CHARS,
    VALIDATION_MIN_CHARS,
    compute_chunking_stats,
    split_text,
)

logger = logging.getLogger(__name__)

PREVIEW_SNIPPET_CHARS = 300
SMALL_CHUNK_THRESHOLD = VALIDATION_MIN_CHARS
LARGE_CHUNK_THRESHOLD = VALIDATION_MAX_CHARS
DEFAULT_MAX_CHARS = SOFT_MAX_CHARS


def build_chunk_preview(
    intake_id: str,
    text: str,
    debug_dir: Path,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> dict:
    """
    Split text with the production splitter and return preview payload + debug files.
    """
    chunks = split_text(text, max_chars=max_chars)
    stats = compute_chunking_stats(chunks)
    counts = [len(c) for c in chunks]

    items: list[dict] = []
    for index, chunk in enumerate(chunks, start=1):
        warning = _chunk_warning(len(chunk))
        items.append(
            {
                "index": index,
                "char_count": len(chunk),
                "preview": _snippet(chunk),
                "full_text": chunk,
                "warning": warning,
            }
        )

    total = len(chunks)
    avg_chars = round(sum(counts) / total, 1) if total else 0.0
    min_chars = min(counts) if counts else 0
    max_chars_found = max(counts) if counts else 0

    payload = {
        "total_chunks": total,
        "avg_chars": avg_chars,
        "min_chars": min_chars,
        "max_chars": max_chars_found,
        "count_below_soft_min": stats.count_below_soft_min,
        "count_above_2500": stats.count_above_hard_warn,
        "chunks": items,
    }

    _save_debug_files(intake_id, debug_dir, items, payload)
    return payload


def _snippet(text: str, limit: int = PREVIEW_SNIPPET_CHARS) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit] + "…"


def _chunk_warning(char_count: int) -> str | None:
    if char_count < SMALL_CHUNK_THRESHOLD:
        return "Too small"
    if char_count > LARGE_CHUNK_THRESHOLD:
        return "Too large"
    return None


def _save_debug_files(intake_id: str, debug_dir: Path, items: list[dict], summary: dict) -> None:
    target = debug_dir / intake_id
    target.mkdir(parents=True, exist_ok=True)

    for item in items:
        filename = f"chunk_{item['index']:04d}.txt"
        (target / filename).write_text(item["full_text"], encoding="utf-8")

    summary_path = target / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Chunk debug saved: %s (%s chunks)", target, len(items))
