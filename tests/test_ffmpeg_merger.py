"""Tests for FFmpeg-based audiobook merge."""

from __future__ import annotations

import shutil
import struct
import wave
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.services.ffmpeg_merger import (
    FFmpegNotFoundError,
    list_chunk_wavs,
    merge_chunks_ffmpeg,
)


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _write_test_wav(path: Path, *, duration_ms: int = 200, sample_rate: int = 24000) -> None:
    num_samples = int(sample_rate * duration_ms / 1000)
    frames = struct.pack(f"<{num_samples}h", *([2000] * num_samples))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)


def test_list_chunk_wavs_sorts_by_index(tmp_path: Path):
    _write_test_wav(tmp_path / "0003.wav")
    _write_test_wav(tmp_path / "0001.wav")
    _write_test_wav(tmp_path / "0002.wav")
    paths = list_chunk_wavs(tmp_path)
    assert [p.name for p in paths] == ["0001.wav", "0002.wav", "0003.wav"]


def test_merge_raises_when_no_chunks(tmp_path: Path):
    with pytest.raises(ValueError, match="No chunk WAV"):
        merge_chunks_ffmpeg("job", str(tmp_path), str(tmp_path / "out.wav"))


def test_merge_raises_when_ffmpeg_missing(tmp_path: Path):
    _write_test_wav(tmp_path / "0001.wav")
    with patch("backend.services.ffmpeg_merger.shutil.which", return_value=None):
        with pytest.raises(FFmpegNotFoundError, match="FFmpeg not installed"):
            merge_chunks_ffmpeg("job", str(tmp_path), str(tmp_path / "final.wav"))


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not on PATH")
def test_merge_chunks_ffmpeg_produces_output(tmp_path: Path):
    chunks_dir = tmp_path / "chunks"
    _write_test_wav(chunks_dir / "0001.wav")
    _write_test_wav(chunks_dir / "0002.wav")
    output = tmp_path / "final_audiobook.wav"

    result = merge_chunks_ffmpeg("intake-1", str(chunks_dir), str(output), apply_loudnorm=False)

    assert result == output.resolve()
    assert output.exists()
    assert output.stat().st_size > 44
    assert (chunks_dir / "0001.wav").exists()
    assert (chunks_dir / "0002.wav").exists()
