"""API schemas for PDF intake (Phase 1)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PageTextSchema(BaseModel):
    page_number: int
    text: str


class PdfUploadResponse(BaseModel):
    intake_id: str
    filename: str
    page_count: int
    pages: list[PageTextSchema]
    full_text: str
    preview_text: str


class PdfTextUpdateRequest(BaseModel):
    full_text: str = Field(..., min_length=1)


class PdfIntakeMessageResponse(BaseModel):
    message: str
    intake_id: str | None = None
