"""Simple JSON file status for in-progress audiobook generation."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class GenerationStatus:
    intake_id: str
    status: str = "idle"
    current_chunk: int = 0
    total_chunks: int = 0
    current_token_index: int = 0
    total_tokens: int = 0
    eta: str = "—"
    output_path: str | None = None
    cancel_requested: bool = False
    error: str | None = None
    started_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


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
        return GenerationStatus(**data)

    def write(self, status: GenerationStatus) -> None:
        path = self.path_for(status.intake_id)
        path.write_text(
            json.dumps(status.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def request_cancel(self, intake_id: str) -> None:
        status = self.read(intake_id)
        if status is None:
            return
        status.cancel_requested = True
        status.status = "cancelling"
        self.write(status)
