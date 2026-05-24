"""Tests for audiobook generation helpers."""

from __future__ import annotations

from pathlib import Path

from backend.services.audiobook_generator import scan_completed_chunks
from backend.services.generation_status import GenerationStatus, chunk_preview_snippet


def test_scan_completed_chunks_empty_dir(tmp_path: Path):
    start, paths = scan_completed_chunks(tmp_path, 5)
    assert start == 1
    assert paths == []


def test_scan_completed_chunks_resume_after_gap(tmp_path: Path):
    (tmp_path / "0001.wav").write_bytes(b"RIFF")
    (tmp_path / "0002.wav").write_bytes(b"RIFF")
    start, paths = scan_completed_chunks(tmp_path, 5)
    assert start == 3
    assert len(paths) == 2


def test_scan_completed_chunks_all_done(tmp_path: Path):
    for i in range(1, 4):
        (tmp_path / f"{i:04d}.wav").write_bytes(b"RIFF")
    start, paths = scan_completed_chunks(tmp_path, 3)
    assert start == 4
    assert len(paths) == 3


def test_chunk_preview_snippet():
    text = "a" * 200
    assert len(chunk_preview_snippet(text)) == 121
    assert chunk_preview_snippet("short") == "short"


def test_generation_status_from_dict_ignores_unknown_keys():
    status = GenerationStatus.from_dict(
        {
            "intake_id": "x",
            "status": "generating",
            "unknown_field": True,
        }
    )
    assert status.intake_id == "x"
    assert status.status == "generating"
