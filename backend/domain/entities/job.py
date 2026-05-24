"""Domain entity: audiobook generation job."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import uuid4


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """Core domain model for a generation job."""

    id: str = field(default_factory=lambda: str(uuid4()))
    status: JobStatus = JobStatus.PENDING
    project_name: str | None = None
    source_pdf_path: str | None = None
    chunk_duration_minutes: int = 4
    current_chunk_index: int = 0
    total_chunks: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # TODO: generation options (preview, trusted_mode, auto_continue)
    # TODO: domain invariants and state transitions
