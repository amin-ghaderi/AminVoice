"""Schemas for chunk preview / debug."""

from __future__ import annotations

from pydantic import BaseModel


class ChunkPreviewItem(BaseModel):
    index: int
    char_count: int
    preview: str
    full_text: str
    warning: str | None = None


class ChunkPreviewResponse(BaseModel):
    total_chunks: int
    avg_chars: float
    min_chars: int
    max_chars: int
    chunks: list[ChunkPreviewItem]
