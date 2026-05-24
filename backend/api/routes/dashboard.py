"""Dashboard UI routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.api.deps import get_app_settings
from backend.config.settings import Settings

router = APIRouter(tags=["dashboard"])


def get_templates(settings: Settings = Depends(get_app_settings)) -> Jinja2Templates:
    return Jinja2Templates(directory=str(settings.frontend_templates_dir))


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    settings: Settings = Depends(get_app_settings),
) -> HTMLResponse:
    templates = Jinja2Templates(directory=str(settings.frontend_templates_dir))
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "app_name": settings.app_name,
            "default_chunk_minutes": 4,
        },
    )
