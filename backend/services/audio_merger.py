"""Merge sequential WAV chunks into one audiobook file."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def merge_wav_files(chunk_paths: list[Path], output_path: Path) -> None:
    from pydub import AudioSegment

    if not chunk_paths:
        raise ValueError("No audio chunks to merge.")

    combined = AudioSegment.empty()
    for path in chunk_paths:
        if not path.exists():
            raise FileNotFoundError(f"Missing chunk: {path}")
        combined += AudioSegment.from_wav(str(path))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.export(str(output_path), format="wav")
    logger.info("Merged %s chunks → %s", len(chunk_paths), output_path)
