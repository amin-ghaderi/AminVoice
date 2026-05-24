"""FastAPI dependency injection placeholders."""

from __future__ import annotations

from backend.config.settings import Settings, get_settings


def get_app_settings() -> Settings:
    return get_settings()

# TODO: get_job_repository()
# TODO: get_job_service()
