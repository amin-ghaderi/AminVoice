"""Settings UI route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.api.deps import get_app_settings
from backend.config.settings import Settings

router = APIRouter(tags=["settings"])


@router.get("/settings", response_class=HTMLResponse)
def settings_page(
    request: Request,
    settings: Settings = Depends(get_app_settings),
) -> HTMLResponse:
    templates = Jinja2Templates(directory=str(settings.frontend_templates_dir))
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={"app_name": settings.app_name},
    )
