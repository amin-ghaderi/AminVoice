"""Repository interface — domain layer contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.entities.job import Job


class JobRepository(ABC):
    @abstractmethod
    def get_by_id(self, job_id: str) -> Job | None:
        ...

    @abstractmethod
    def save(self, job: Job) -> Job:
        ...

    @abstractmethod
    def list_recent(self, limit: int = 20) -> list[Job]:
        ...

    # TODO: find resumable jobs, delete, update progress
