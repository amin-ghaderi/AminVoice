"""Schemas for post-generation audio quality report."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AudioQualityReportResponse(BaseModel):
    intake_id: str
    chunk_count: int
    avg_chunk_silence_ratio: float
    discontinuities_count: int
    loudness_variance: float
    chunk_variation_score: float
    quality_label: str
    per_chunk_loudness_dbfs: list[float] = Field(default_factory=list)
    per_chunk_silence_ratio: list[float] = Field(default_factory=list)
