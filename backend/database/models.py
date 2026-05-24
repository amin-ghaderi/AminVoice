"""ORM models — schema placeholders for future job persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base


class JobRecord(Base):
    """Persistence model for an audiobook generation job."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    project_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_duration_minutes: Mapped[int] = mapped_column(default=4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # TODO: add columns for progress, options (preview, trusted, auto_continue), metadata
