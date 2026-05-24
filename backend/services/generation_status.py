"""Simple JSON file status for in-progress audiobook generation."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


def chunk_preview_snippet(text: str, limit: int = 120) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit] + "…"


@dataclass
class GenerationStatus:
    intake_id: str
    status: str = "idle"
    status_label: str = "—"
    current_chunk: int = 0
    total_chunks: int = 0
    current_chunk_size: int = 0
    current_chunk_preview: str = ""
    progress_percent: float = 0.0
    current_token_index: int = 0
    current_token_name: str = ""
    total_tokens: int = 0
    quota_failovers: int = 0
    eta: str = "—"
    wait_seconds: int = 0
    output_path: str | None = None
    cancel_requested: bool = False
    error: str | None = None
    started_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    def set_chunk_progress(self, index: int, chunk_text: str) -> None:
        self.current_chunk = index
        self.current_chunk_size = len(chunk_text)
        self.current_chunk_preview = chunk_preview_snippet(chunk_text)
        if self.total_chunks > 0:
            self.progress_percent = round((index / self.total_chunks) * 100, 1)
        else:
            self.progress_percent = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> GenerationStatus:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


class GenerationStatusStore:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, intake_id: str) -> Path:
        return self._base_dir / f"{intake_id}.json"

    def read(self, intake_id: str) -> GenerationStatus | None:
        path = self.path_for(intake_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return GenerationStatus.from_dict(data)

    def write(self, status: GenerationStatus) -> None:
        path = self.path_for(status.intake_id)
        path.write_text(
            json.dumps(status.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def find_active(self) -> GenerationStatus | None:
        """Return the most recently updated in-progress generation, if any."""
        active_statuses = ("generating", "waiting_quota", "merging", "cancelling")
        best: GenerationStatus | None = None
        best_mtime = 0.0
        for path in self._base_dir.glob("*.json"):
            try:
                mtime = path.stat().st_mtime
                data = json.loads(path.read_text(encoding="utf-8"))
                status = GenerationStatus.from_dict(data)
            except (OSError, json.JSONDecodeError):
                continue
            if status.status not in active_statuses:
                continue
            if mtime >= best_mtime:
                best = status
                best_mtime = mtime
        return best

    def request_cancel(self, intake_id: str) -> None:
        status = self.read(intake_id)
        if status is None:
            return
        status.cancel_requested = True
        status.status = "cancelling"
        status.status_label = "Cancelling after current chunk…"
        self.write(status)
