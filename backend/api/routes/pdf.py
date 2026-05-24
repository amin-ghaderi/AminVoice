"""PDF upload and text preview endpoints (Phase 1)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.api.deps import get_pdf_intake_service
from backend.schemas.pdf_intake import (
    PdfIntakeMessageResponse,
    PdfTextUpdateRequest,
    PdfUploadResponse,
    PageTextSchema,
)
from backend.services.pdf_extractor import PdfExtractionError
from backend.services.pdf_intake_service import PdfIntakeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pdf", tags=["pdf"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post("/upload", response_model=PdfUploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    service: PdfIntakeService = Depends(get_pdf_intake_service),
) -> PdfUploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="A PDF file is required.")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds maximum upload size (50 MB).")
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        payload = service.process_upload(data, filename=file.filename)
    except PdfExtractionError as exc:
        logger.error("PDF extraction failed for %s: %s", file.filename, exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _to_response(payload)


@router.put("/{intake_id}/text", response_model=PdfUploadResponse)
def update_extracted_text(
    intake_id: str,
    body: PdfTextUpdateRequest,
    service: PdfIntakeService = Depends(get_pdf_intake_service),
) -> PdfUploadResponse:
    try:
        payload = service.update_text(intake_id, body.full_text)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(payload)


@router.delete("/{intake_id}", response_model=PdfIntakeMessageResponse)
def cancel_intake(
    intake_id: str,
    service: PdfIntakeService = Depends(get_pdf_intake_service),
) -> PdfIntakeMessageResponse:
    service.delete_intake(intake_id)
    return PdfIntakeMessageResponse(message="Intake cancelled.", intake_id=intake_id)


def _to_response(payload) -> PdfUploadResponse:
    return PdfUploadResponse(
        intake_id=payload.intake_id,
        filename=payload.filename,
        page_count=payload.page_count,
        pages=[PageTextSchema(**p) for p in payload.pages],
        full_text=payload.full_text,
        preview_text=payload.preview_text,
        repair_applied=payload.repair_applied,
        repair_fix_count=payload.repair_fix_count,
    )
