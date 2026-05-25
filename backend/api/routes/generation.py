"""Audiobook generation endpoints (Phase 3 — sequential TTS)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.api.deps import get_audiobook_generator, get_app_settings, get_pdf_intake_service
from backend.config.settings import Settings
from backend.schemas.chunk_preview import ChunkPreviewResponse
from backend.schemas.audio_quality import AudioQualityReportResponse
from backend.schemas.generation import (
    GenerationContinueRequest,
    GenerationStartResponse,
    GenerationStatusResponse,
)
from backend.services.audiobook_generator import AudiobookGenerator
from backend.services.scene_context import SceneContext, build_scene_context
from backend.services.chunk_preview_service import build_chunk_preview
from backend.services.pdf_intake_service import PdfIntakeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pdf", tags=["generation"])

_active_lock = threading.Lock()
_active_jobs: set[str] = set()


def _run_generation(
    generator: AudiobookGenerator,
    intake_id: str,
    text: str,
    project_name: str,
    scene_context: SceneContext | None = None,
    validation_max_chars: int | None = None,
) -> None:
    try:
        generator.run(
            intake_id,
            text,
            project_name,
            scene_context=scene_context,
            validation_max_chars=validation_max_chars,
        )
    except Exception as exc:
        logger.exception("Generation crashed for %s", intake_id)
        generator._fail(intake_id, str(exc))
    finally:
        with _active_lock:
            _active_jobs.discard(intake_id)


@router.post("/{intake_id}/chunk-preview", response_model=ChunkPreviewResponse)
def chunk_preview(
    intake_id: str,
    intake_service: PdfIntakeService = Depends(get_pdf_intake_service),
    settings: Settings = Depends(get_app_settings),
) -> ChunkPreviewResponse:
    payload = intake_service.get_intake(intake_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Intake session not found.")

    if not payload.full_text.strip():
        raise HTTPException(status_code=400, detail="No text available to chunk.")

    debug_dir = settings.storage_root / "debug" / "chunks"
    result = build_chunk_preview(intake_id, payload.full_text, debug_dir)
    return ChunkPreviewResponse(**result)


@router.post("/{intake_id}/continue", response_model=GenerationStartResponse)
def continue_to_generation(
    intake_id: str,
    background_tasks: BackgroundTasks,
    intake_service: PdfIntakeService = Depends(get_pdf_intake_service),
    generator: AudiobookGenerator = Depends(get_audiobook_generator),
    body: GenerationContinueRequest | None = Body(default=None),
) -> GenerationStartResponse:
    payload = intake_service.get_intake(intake_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Intake session not found.")

    with _active_lock:
        if intake_id in _active_jobs:
            raise HTTPException(status_code=409, detail="Generation already running.")
        _active_jobs.add(intake_id)

    from backend.services.text_splitter import resolve_validation_max_chars, split_text

    validation_max = resolve_validation_max_chars(
        body.validation_max_chars if body else None
    )
    chunks = split_text(payload.full_text, validation_max_chars=validation_max)
    if not chunks:
        with _active_lock:
            _active_jobs.discard(intake_id)
        raise HTTPException(status_code=400, detail="No text available for generation.")

    scene_context = build_scene_context(
        use_scene=body.use_scene if body else False,
        scene=body.scene if body else None,
        style=body.style if body else None,
        tone=body.tone if body else None,
    )
    logger.info("Scene mode: %s", scene_context.is_enabled())
    logger.info("Scene config: %s", scene_context)
    logger.info("Chunk validation_max_chars=%s (total_chunks=%s)", validation_max, len(chunks))

    background_tasks.add_task(
        _run_generation,
        generator,
        intake_id,
        payload.full_text,
        payload.filename,
        scene_context,
        validation_max,
    )

    return GenerationStartResponse(
        message="Generation started.",
        intake_id=intake_id,
        total_chunks=len(chunks),
    )


@router.get("/{intake_id}/generation/status", response_model=GenerationStatusResponse)
def generation_status(
    intake_id: str,
    generator: AudiobookGenerator = Depends(get_audiobook_generator),
) -> GenerationStatusResponse:
    status = generator.status_store.read(intake_id)
    if status is None:
        raise HTTPException(status_code=404, detail="No generation status found.")
    return GenerationStatusResponse(
        intake_id=status.intake_id,
        status=status.status,
        status_label=status.status_label,
        current_chunk=status.current_chunk,
        total_chunks=status.total_chunks,
        current_chunk_size=status.current_chunk_size,
        current_chunk_preview=status.current_chunk_preview,
        progress_percent=status.progress_percent,
        current_token_index=status.current_token_index,
        total_tokens=status.total_tokens,
        eta=status.eta,
        wait_seconds=status.wait_seconds,
        output_path=status.output_path,
        error=status.error,
    )


@router.post("/{intake_id}/generation/cancel")
def cancel_generation(
    intake_id: str,
    generator: AudiobookGenerator = Depends(get_audiobook_generator),
) -> dict:
    generator.status_store.request_cancel(intake_id)
    return {"message": "Cancel requested.", "intake_id": intake_id}


@router.get("/{intake_id}/audio-quality", response_model=AudioQualityReportResponse)
def audio_quality_report(
    intake_id: str,
    generator: AudiobookGenerator = Depends(get_audiobook_generator),
) -> AudioQualityReportResponse:
    report = generator.quality_store.read(intake_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Audio quality report not available.")
    return AudioQualityReportResponse(**report.to_dict())


@router.get("/{intake_id}/audiobook/download")
def download_audiobook(
    intake_id: str,
    generator: AudiobookGenerator = Depends(get_audiobook_generator),
    settings: Settings = Depends(get_app_settings),
) -> FileResponse:
    status = generator.status_store.read(intake_id)
    if status is None or status.status != "completed":
        raise HTTPException(status_code=404, detail="Audiobook not ready.")

    path = Path(status.output_path) if status.output_path else None
    if path is None or not path.exists():
        path = settings.outputs_dir / intake_id / "final_audiobook.wav"
    if not path.exists():
        path = settings.outputs_dir / f"{intake_id}_final_audiobook.wav"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Output file missing.")

    return FileResponse(
        path,
        media_type="audio/wav",
        filename="final_audiobook.wav",
    )
