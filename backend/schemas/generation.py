"""Schemas for audiobook generation status."""

from __future__ import annotations

from pydantic import BaseModel


class GenerationStatusResponse(BaseModel):
    intake_id: str
    status: str
    current_chunk: int
    total_chunks: int
    current_token_index: int
    total_tokens: int
    eta: str
    output_path: str | None = None
    error: str | None = None


class GenerationStartResponse(BaseModel):
    message: str
    intake_id: str
    total_chunks: int
