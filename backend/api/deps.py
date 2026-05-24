"""FastAPI dependency injection placeholders."""

from __future__ import annotations

from functools import lru_cache

from backend.config.settings import Settings, get_settings
from backend.services.audiobook_generator import AudiobookGenerator
from backend.services.pdf_intake_service import PdfIntakeService


def get_app_settings() -> Settings:
    return get_settings()


@lru_cache
def get_pdf_intake_service() -> PdfIntakeService:
    return PdfIntakeService(get_settings())


@lru_cache
def get_audiobook_generator() -> AudiobookGenerator:
    return AudiobookGenerator(get_settings())

# TODO: get_job_repository()
# TODO: get_job_service()
