"""Schemas for audiobook generation status."""

from __future__ import annotations

from pydantic import BaseModel


class GenerationStatusResponse(BaseModel):
    intake_id: str
    status: str
    status_label: str
    current_chunk: int
    total_chunks: int
    current_chunk_size: int
    current_chunk_preview: str
    progress_percent: float
    current_token_index: int
    total_tokens: int
    eta: str
    wait_seconds: int = 0
    output_path: str | None = None
    error: str | None = None


class GenerationContinueRequest(BaseModel):
    """Optional scene settings when starting generation (Phase 5.2)."""

    scene: str | None = None
    style: str | None = None
    tone: str | None = None
    use_scene: bool = False


class GenerationStartResponse(BaseModel):
    message: str
    intake_id: str
    total_chunks: int
