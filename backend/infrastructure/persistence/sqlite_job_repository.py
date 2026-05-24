"""SQLite implementation of JobRepository — placeholder."""

from __future__ import annotations

from backend.domain.entities.job import Job
from backend.domain.repositories.job_repository import JobRepository


class SqliteJobRepository(JobRepository):
    """Persists jobs via SQLAlchemy."""

    def get_by_id(self, job_id: str) -> Job | None:
        # TODO: map JobRecord <-> Job entity
        raise NotImplementedError

    def save(self, job: Job) -> Job:
        # TODO: implement persistence
        raise NotImplementedError

    def list_recent(self, limit: int = 20) -> list[Job]:
        # TODO: implement query
        raise NotImplementedError
