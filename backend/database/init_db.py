"""SQLite database bootstrap."""

from __future__ import annotations

import logging

from backend.database.base import Base, get_engine
from backend.database import models  # noqa: F401 — register ORM models

logger = logging.getLogger(__name__)


def init_database() -> None:
    """Create tables if they do not exist."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")
