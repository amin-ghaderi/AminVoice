"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.api.router import api_router
from backend.config.settings import get_settings
from backend.database.init_db import init_database
from backend.utils.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    settings.ensure_storage_dirs()
    init_database()
    logger.info("Application started: %s", settings.app_name)
    yield
    logger.info("Application shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.mount(
        "/static",
        StaticFiles(directory=str(settings.frontend_static_dir)),
        name="static",
    )

    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/dashboard")

    return app


app = create_app()
