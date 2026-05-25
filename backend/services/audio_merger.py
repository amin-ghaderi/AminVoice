"""Merge sequential WAV chunks with stitch smoothing (post-TTS only)."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 24_000
TARGET_CHANNELS = 1
TARGET_DBFS = -20.0

DEFAULT_CROSSFADE_MS = 80
MIN_CROSSFADE_MS = 50
MAX_CROSSFADE_MS = 120

# Leading/trailing silence trim (per chunk).
SILENCE_THRESH_DBFS = -45
SILENCE_MIN_LEN_MS = 80


def merge_wav_files(
    chunk_paths: list[Path],
    output_path: Path,
    *,
    crossfade_ms: int = DEFAULT_CROSSFADE_MS,
    target_dbfs: float = TARGET_DBFS,
) -> None:
    """
    Merge chunk WAVs into one audiobook with crossfade, loudness, and format normalization.
    """
    from pydub import AudioSegment
    from pydub.effects import strip_silence

    if not chunk_paths:
        raise ValueError("No audio chunks to merge.")

    fade_ms = _clamp_crossfade(crossfade_ms)
    prepared: list[AudioSegment] = []

    for path in chunk_paths:
        if not path.exists():
            raise FileNotFoundError(f"Missing chunk: {path}")
        segment = AudioSegment.from_wav(str(path))
        segment = _to_target_format(segment)
        segment = strip_silence(
            segment,
            silence_len=SILENCE_MIN_LEN_MS,
            silence_thresh=SILENCE_THRESH_DBFS,
        )
        segment = normalize_to_target_dbfs(segment, target_dbfs)
        prepared.append(segment)
        logger.debug(
            "Prepared chunk %s: %sms, %s Hz, dBFS=%.1f",
            path.name,
            len(segment),
            segment.frame_rate,
            segment.dBFS,
        )

    if not prepared:
        raise ValueError("No audio content after chunk preparation.")

    combined = prepared[0]
    for segment in prepared[1:]:
        combined = combined.append(segment, crossfade=fade_ms)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.export(str(output_path), format="wav")
    logger.info(
        "Merged %s chunks → %s (crossfade=%sms, target=%s dBFS, %s Hz mono)",
        len(prepared),
        output_path,
        fade_ms,
        target_dbfs,
        TARGET_SAMPLE_RATE,
    )


def _clamp_crossfade(ms: int) -> int:
    return max(MIN_CROSSFADE_MS, min(MAX_CROSSFADE_MS, ms))


def _to_target_format(segment):
    """Force 24 kHz mono before merge."""
    return segment.set_frame_rate(TARGET_SAMPLE_RATE).set_channels(TARGET_CHANNELS)


def normalize_to_target_dbfs(segment, target_dbfs: float = TARGET_DBFS):
    """Match perceived loudness to a target RMS level (dBFS)."""
    if segment.max_dBFS == float("-inf"):
        return segment
    gain = target_dbfs - segment.dBFS
    return segment.apply_gain(gain)
