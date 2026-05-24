"""Health check routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.deps import get_app_settings
from backend.config.settings import Settings
from backend.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(settings: Settings = Depends(get_app_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.app_env,
    )
