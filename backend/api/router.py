"""Aggregate API routers."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.routes import dashboard, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(dashboard.router)

# TODO: api_router.include_router(jobs.router, prefix="/api/v1/jobs")
