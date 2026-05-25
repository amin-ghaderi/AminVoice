"""Heuristic audio quality metrics for audiobook chunks (stdlib wave only)."""

from __future__ import annotations

import json
import logging
import math
import statistics
import struct
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

SILENCE_RMS_THRESHOLD = 500
BOUNDARY_WINDOW_MS = 100
DISCONTINUITY_RMS_DELTA = 2500
BOUNDARY_SILENCE_JUMP = 4500


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


@dataclass
class _WavMetrics:
    samples: list[int]
    sample_rate: int

    @property
    def duration_ms(self) -> int:
        if self.sample_rate <= 0:
            return 0
        return int(len(self.samples) * 1000 / self.sample_rate)


def _load_wav_mono(path: Path) -> _WavMetrics:
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frames = wav_file.readframes(wav_file.getnframes())

    if sample_width != 2:
        raise ValueError(f"Unsupported sample width {sample_width} in {path}")

    count = len(frames) // 2
    samples = list(struct.unpack(f"<{count}h", frames[: count * 2]))
    if channels > 1:
        samples = samples[::channels]
    return _WavMetrics(samples=samples, sample_rate=sample_rate)


def _rms(samples: list[int]) -> float:
    if not samples:
        return 0.0
    mean_sq = sum(s * s for s in samples) / len(samples)
    return math.sqrt(mean_sq)


def _rms_to_dbfs(rms: float) -> float:
    if rms <= 0:
        return -90.0
    return 20.0 * math.log10(rms / 32768.0)


def _silence_ratio(metrics: _WavMetrics, window_ms: int = 10) -> float:
    if not metrics.samples or metrics.sample_rate <= 0:
        return 1.0
    window_size = max(1, int(metrics.sample_rate * window_ms / 1000))
    quiet = 0
    total = 0
    for start in range(0, len(metrics.samples), window_size):
        window = metrics.samples[start : start + window_size]
        if not window:
            continue
        total += 1
        if _rms(window) <= SILENCE_RMS_THRESHOLD:
            quiet += 1
    return quiet / total if total else 0.0


def _window_samples(metrics: _WavMetrics, *, end: bool) -> list[int]:
    if metrics.sample_rate > 0:
        window_size = int(metrics.sample_rate * BOUNDARY_WINDOW_MS / 1000)
    else:
        window_size = 2400
    window_size = max(1, min(window_size, len(metrics.samples)))
    if window_size <= 0:
        return []
    if end:
        return metrics.samples[-window_size:]
    return metrics.samples[:window_size]


def _is_discontinuity(tail: list[int], head: list[int]) -> bool:
    tail_rms = _rms(tail)
    head_rms = _rms(head)
    if abs(tail_rms - head_rms) >= DISCONTINUITY_RMS_DELTA:
        return True
    tail_quiet = tail_rms <= SILENCE_RMS_THRESHOLD
    head_quiet = head_rms <= SILENCE_RMS_THRESHOLD
    if tail_quiet != head_quiet:
        return True
    if not tail_quiet and not head_quiet and abs(tail_rms - head_rms) >= BOUNDARY_SILENCE_JUMP:
        return True
    return False


def analyze_chunks(chunk_paths: list[Path], intake_id: str) -> AudioQualityReport:
    """Compute heuristic quality metrics from per-chunk WAV files."""
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

    metrics_list: list[_WavMetrics] = []
    silence_ratios: list[float] = []
    loudness_values: list[float] = []

    for path in chunk_paths:
        if not path.exists():
            continue
        try:
            metrics = _load_wav_mono(path)
        except (wave.Error, ValueError) as exc:
            logger.warning("Skipping quality analysis for %s: %s", path, exc)
            continue
        metrics_list.append(metrics)
        silence_ratios.append(_silence_ratio(metrics))
        loudness_values.append(_rms_to_dbfs(_rms(metrics.samples)))

    discontinuities = _count_discontinuities(metrics_list)
    avg_silence = statistics.mean(silence_ratios) if silence_ratios else 0.0
    loudness_var = (
        statistics.pvariance(loudness_values) if len(loudness_values) > 1 else 0.0
    )
    variation_score = _chunk_variation_score(loudness_values)

    report = AudioQualityReport(
        intake_id=intake_id,
        chunk_count=len(metrics_list),
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


def _count_discontinuities(metrics_list: list[_WavMetrics]) -> int:
    if len(metrics_list) < 2:
        return 0
    count = 0
    for index in range(len(metrics_list) - 1):
        tail = _window_samples(metrics_list[index], end=True)
        head = _window_samples(metrics_list[index + 1], end=False)
        if _is_discontinuity(tail, head):
            count += 1
    return count


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
