"""Tests for audiobook stitch / merge post-processing."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from backend.services.audio_merger import (
    DEFAULT_CROSSFADE_MS,
    MAX_CROSSFADE_MS,
    MIN_CROSSFADE_MS,
    TARGET_DBFS,
    _clamp_crossfade,
)

pydub = pytest.importorskip("pydub")
from pydub import AudioSegment
from pydub.generators import Sine

from backend.services.audio_merger import (
    TARGET_SAMPLE_RATE,
    merge_wav_files,
    normalize_to_target_dbfs,
)


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def test_clamp_crossfade():
    assert _clamp_crossfade(80) == 80
    assert _clamp_crossfade(10) == MIN_CROSSFADE_MS
    assert _clamp_crossfade(500) == MAX_CROSSFADE_MS


def test_normalize_to_target_dbfs():
    tone = Sine(440).to_audio_segment(duration=200).apply_gain(-6)
    normalized = normalize_to_target_dbfs(tone, TARGET_DBFS)
    assert abs(normalized.dBFS - TARGET_DBFS) < 1.5


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg required for wav export")
def test_merge_applies_format_and_exports(tmp_path: Path):
    chunk_a = tmp_path / "0001.wav"
    chunk_b = tmp_path / "0002.wav"
    out = tmp_path / "final_audiobook.wav"

    seg = Sine(440).to_audio_segment(duration=300).apply_gain(-8)
    seg = seg.set_frame_rate(TARGET_SAMPLE_RATE).set_channels(1)
    seg.export(str(chunk_a), format="wav")

    seg_b = Sine(330).to_audio_segment(duration=300).apply_gain(-8)
    seg_b = seg_b.set_frame_rate(TARGET_SAMPLE_RATE).set_channels(1)
    seg_b.export(str(chunk_b), format="wav")

    merge_wav_files([chunk_a, chunk_b], out, crossfade_ms=DEFAULT_CROSSFADE_MS)

    assert out.exists()
    merged = AudioSegment.from_wav(str(out))
    assert merged.frame_rate == TARGET_SAMPLE_RATE
    assert merged.channels == 1
    assert len(merged) > 400
