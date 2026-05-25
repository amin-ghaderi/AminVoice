"""Heuristic audio quality metrics for merged audiobook chunks (no ML)."""

from __future__ import annotations

import json
import logging
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

SILENCE_THRESH_DBFS = -45
BOUNDARY_WINDOW_MS = 100
DISCONTINUITY_DB_DELTA = 10.0
BOUNDARY_SILENCE_JUMP_DB = 18.0


@dataclass
class AudioQualityReport:
    intake_id: str
    chunk_count: int
    avg_chunk_silence_ratio: float
    discontinuities_count: int
    loudness_variance: float
    chunk_variation_score: float
    per_chunk_loudness_dbfs: list[float] = field(default_factory=list)
    per_chunk_silence_ratio: list[float] = field(default_factory=list)
    quality_label: str = "good"

    def to_dict(self) -> dict:
        return asdict(self)


class AudioQualityReportStore:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, intake_id: str) -> Path:
        return self._base_dir / f"{intake_id}.json"

    def write(self, report: AudioQualityReport) -> Path:
        path = self.path_for(report.intake_id)
        path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def read(self, intake_id: str) -> AudioQualityReport | None:
        path = self.path_for(intake_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return AudioQualityReport(**data)


def analyze_chunks(chunk_paths: list[Path], intake_id: str) -> AudioQualityReport:
    """Compute heuristic quality metrics from per-chunk WAV files."""
    from pydub import AudioSegment

    if not chunk_paths:
        return AudioQualityReport(
            intake_id=intake_id,
            chunk_count=0,
            avg_chunk_silence_ratio=0.0,
            discontinuities_count=0,
            loudness_variance=0.0,
            chunk_variation_score=0.0,
            quality_label="unknown",
        )

    segments: list = []
    silence_ratios: list[float] = []
    loudness_values: list[float] = []

    for path in chunk_paths:
        if not path.exists():
            continue
        segment = AudioSegment.from_wav(str(path))
        segment = segment.set_frame_rate(24_000).set_channels(1)
        segments.append(segment)
        silence_ratios.append(_silence_ratio(segment))
        loudness_values.append(_safe_dbfs(segment))

    discontinuities = _count_discontinuities(segments)
    avg_silence = statistics.mean(silence_ratios) if silence_ratios else 0.0
    loudness_var = (
        statistics.pvariance(loudness_values) if len(loudness_values) > 1 else 0.0
    )
    variation_score = _chunk_variation_score(loudness_values)

    report = AudioQualityReport(
        intake_id=intake_id,
        chunk_count=len(segments),
        avg_chunk_silence_ratio=round(avg_silence, 4),
        discontinuities_count=discontinuities,
        loudness_variance=round(loudness_var, 2),
        chunk_variation_score=round(variation_score, 1),
        per_chunk_loudness_dbfs=[round(v, 1) for v in loudness_values],
        per_chunk_silence_ratio=[round(v, 4) for v in silence_ratios],
        quality_label=_quality_label(avg_silence, discontinuities, loudness_var, variation_score),
    )
    logger.info(
        "Audio quality report %s: silence=%.2f%% discontinuities=%s variation=%s label=%s",
        intake_id,
        avg_silence * 100,
        discontinuities,
        variation_score,
        report.quality_label,
    )
    return report


def _silence_ratio(segment, window_ms: int = 10) -> float:
    if len(segment) == 0:
        return 1.0
    quiet_windows = 0
    total_windows = 0
    for start in range(0, len(segment), window_ms):
        window = segment[start : start + window_ms]
        if len(window) == 0:
            continue
        total_windows += 1
        if window.max_dBFS == float("-inf") or window.dBFS <= SILENCE_THRESH_DBFS:
            quiet_windows += 1
    return quiet_windows / total_windows if total_windows else 0.0


def _safe_dbfs(segment) -> float:
    if segment.max_dBFS == float("-inf"):
        return SILENCE_THRESH_DBFS
    return float(segment.dBFS)


def _count_discontinuities(segments: list) -> int:
    if len(segments) < 2:
        return 0

    count = 0
    for index in range(len(segments) - 1):
        tail = _window(segments[index], end=True)
        head = _window(segments[index + 1], end=False)
        if _is_discontinuity(tail, head):
            count += 1
    return count


def _window(segment, *, end: bool):
    duration = min(BOUNDARY_WINDOW_MS, len(segment))
    if duration <= 0:
        return segment
    if end:
        return segment[-duration:]
    return segment[:duration]


def _is_discontinuity(tail, head) -> bool:
    tail_db = _safe_dbfs(tail)
    head_db = _safe_dbfs(head)
    if abs(tail_db - head_db) >= DISCONTINUITY_DB_DELTA:
        return True
    tail_peak = tail.max_dBFS
    head_peak = head.max_dBFS
    if tail_peak == float("-inf") and head_peak > SILENCE_THRESH_DBFS:
        return True
    if head_peak == float("-inf") and tail_peak > SILENCE_THRESH_DBFS:
        return True
    if tail_peak > SILENCE_THRESH_DBFS and head_peak > SILENCE_THRESH_DBFS:
        if abs(tail_peak - head_peak) >= BOUNDARY_SILENCE_JUMP_DB:
            return True
    return False


def _chunk_variation_score(loudness_values: list[float]) -> float:
    if len(loudness_values) < 2:
        return 0.0
    deltas = [
        abs(loudness_values[i + 1] - loudness_values[i])
        for i in range(len(loudness_values) - 1)
    ]
    mean_delta = statistics.mean(deltas)
    return min(100.0, mean_delta * 4.0)


def _quality_label(
    avg_silence: float,
    discontinuities: int,
    loudness_var: float,
    variation_score: float,
) -> str:
    issues = 0
    if avg_silence > 0.25:
        issues += 1
    if discontinuities > 0:
        issues += 1
    if loudness_var > 12:
        issues += 1
    if variation_score > 35:
        issues += 1
    if issues == 0:
        return "good"
    if issues <= 2:
        return "fair"
    return "needs_review"
