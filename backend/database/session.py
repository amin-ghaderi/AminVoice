"""Database session dependency for the API layer."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from backend.database.base import get_session_factory


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
