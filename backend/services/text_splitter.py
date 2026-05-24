"""Semantic Persian-aware text splitting for audiobook TTS chunks."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Sizing (chars) — tuned for ~80–180 chunks on a 112-page Persian book.
SOFT_MIN_CHARS = 350
SOFT_MAX_CHARS = 2000
HARD_MAX_CHARS = 2800

# Persian-aware sentence boundaries (delimiter kept on the left segment).
_SENTENCE_SPLIT = re.compile(
    r"(?<=[؟!؛.۔:…])\s+|(?<=[?!;])\s+"
)

_DEFAULT_SOFT_MAX = SOFT_MAX_CHARS


@dataclass(frozen=True)
class ChunkingStats:
    total_chunks: int
    avg_chunk_length: float
    min_chunk_length: int
    max_chunk_length: int
    count_below_soft_min: int
    count_above_hard_warn: int

    def to_dict(self) -> dict:
        return {
            "total_chunks": self.total_chunks,
            "avg_chunk_length": self.avg_chunk_length,
            "min_chunk_length": self.min_chunk_length,
            "max_chunk_length": self.max_chunk_length,
            "count_below_soft_min": self.count_below_soft_min,
            "count_above_2500": self.count_above_hard_warn,
        }


def split_text(text: str, max_chars: int | None = None) -> list[str]:
    """
    Split text into narration chunks using hierarchical semantic boundaries.

    Priority: paragraph (\\n\\n) → sentence → single newline (weak) → hard split.
    ``max_chars`` overrides soft max when provided (legacy API); hard cap still applies.
    """
    soft_max = max_chars if max_chars is not None else _DEFAULT_SOFT_MAX
    soft_max = min(soft_max, HARD_MAX_CHARS)

    cleaned = _strip_page_markers(text).strip()
    if not cleaned:
        return []

    units = _build_semantic_units(cleaned, soft_max)
    chunks = _pack_units(units, soft_max=soft_max, hard_max=HARD_MAX_CHARS)
    chunks = _merge_small_chunks(chunks, soft_min=SOFT_MIN_CHARS, hard_max=HARD_MAX_CHARS)

    stats = compute_chunking_stats(chunks)
    log_chunking_stats(stats)
    return chunks


def compute_chunking_stats(chunks: list[str]) -> ChunkingStats:
    lengths = [len(c) for c in chunks]
    if not lengths:
        return ChunkingStats(0, 0.0, 0, 0, 0, 0)
    return ChunkingStats(
        total_chunks=len(lengths),
        avg_chunk_length=round(sum(lengths) / len(lengths), 1),
        min_chunk_length=min(lengths),
        max_chunk_length=max(lengths),
        count_below_soft_min=sum(1 for n in lengths if n < SOFT_MIN_CHARS),
        count_above_hard_warn=sum(1 for n in lengths if n > 2500),
    )


def log_chunking_stats(stats: ChunkingStats) -> None:
    logger.info(
        "Chunking stats: total=%s avg=%s min=%s max=%s below_%s=%s above_2500=%s",
        stats.total_chunks,
        stats.avg_chunk_length,
        stats.min_chunk_length,
        stats.max_chunk_length,
        SOFT_MIN_CHARS,
        stats.count_below_soft_min,
        stats.count_above_hard_warn,
    )


def _strip_page_markers(text: str) -> str:
    return re.sub(r"^--- Page \d+ ---\s*\n?", "", text, flags=re.MULTILINE)


def _normalize_inline_breaks(block: str) -> str:
    """Single newlines are weak separators — join into flowing prose."""
    lines = [line.strip() for line in block.split("\n") if line.strip()]
    return " ".join(lines)


def _build_semantic_units(text: str, soft_max: int) -> list[str]:
    """Paragraph-first units; split oversized paragraphs into sentences."""
    units: list[str] = []
    paragraphs = re.split(r"\n\s*\n", text)

    for paragraph in paragraphs:
        normalized = _normalize_inline_breaks(paragraph)
        if not normalized:
            continue

        if len(normalized) <= soft_max:
            units.append(normalized)
            continue

        for sentence in _split_sentences(normalized):
            if len(sentence) <= soft_max:
                units.append(sentence)
            else:
                units.extend(_hard_split(sentence, soft_max))

    return units


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split(text)
    return [part.strip() for part in parts if part.strip()]


def _pack_units(units: list[str], *, soft_max: int, hard_max: int) -> list[str]:
    """Greedy pack semantic units; prefer fewer, larger chunks."""
    chunks: list[str] = []
    current = ""

    for unit in units:
        if not unit:
            continue

        if not current:
            current = unit
            continue

        combined_len = len(current) + 1 + len(unit)

        if combined_len <= soft_max:
            current = f"{current} {unit}"
            continue

        # Avoid leaving a tiny trailing chunk: allow soft overflow up to hard max.
        if len(current) < SOFT_MIN_CHARS and combined_len <= hard_max:
            current = f"{current} {unit}"
            continue

        chunks.append(current)
        current = unit

    if current:
        chunks.append(current)

    # Safety: nothing may exceed hard max.
    final: list[str] = []
    for chunk in chunks:
        if len(chunk) <= hard_max:
            final.append(chunk)
        else:
            final.extend(_hard_split(chunk, hard_max))
    return final


def _merge_small_chunks(
    chunks: list[str],
    *,
    soft_min: int,
    hard_max: int,
) -> list[str]:
    if len(chunks) < 2:
        return chunks

    merged: list[str] = []
    for chunk in chunks:
        if not merged:
            merged.append(chunk)
            continue

        if len(chunk) >= soft_min:
            merged.append(chunk)
            continue

        prev = merged[-1]
        if len(prev) + 1 + len(chunk) <= hard_max:
            merged[-1] = f"{prev} {chunk}"
            continue

        merged.append(chunk)

    # Forward pass: merge stranded small tail into previous when possible.
    if len(merged) >= 2 and len(merged[-1]) < soft_min:
        tail = merged.pop()
        prev = merged[-1]
        if len(prev) + 1 + len(tail) <= hard_max:
            merged[-1] = f"{prev} {tail}"
        else:
            merged.append(tail)

    return merged


def _hard_split(text: str, max_chars: int) -> list[str]:
    """Last-resort split at spaces (never mid-word when avoidable)."""
    if len(text) <= max_chars:
        return [text]

    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            space = text.rfind(" ", start, end)
            if space > start + max_chars // 2:
                end = space
        piece = text[start:end].strip()
        if piece:
            parts.append(piece)
        start = max(end, start + 1)
    return parts
