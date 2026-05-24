"""Tests for chunk preview service."""

from __future__ import annotations

from pathlib import Path

from backend.services.chunk_preview_service import build_chunk_preview
from backend.services.text_splitter import split_text


def test_chunk_preview_matches_splitter(tmp_path: Path):
    text = "پاراگراف اول.\n\nپاراگراف دوم با جمله دیگر."
    expected = split_text(text)
    result = build_chunk_preview("test-id", text, tmp_path)

    assert result["total_chunks"] == len(expected)
    assert len(result["chunks"]) == len(expected)
    for item, chunk in zip(result["chunks"], expected, strict=True):
        assert item["full_text"] == chunk
        assert item["char_count"] == len(chunk)


def test_chunk_preview_warnings(tmp_path: Path):
    small_result = build_chunk_preview("warn-small", "x" * 150, tmp_path)
    assert small_result["chunks"][0]["warning"] == "Too small"

    # Soft packing caps near 2000; use a single block above the UI warn threshold.
    large_result = build_chunk_preview("warn-large", "z" * 2700, tmp_path, max_chars=2700)
    assert any(c["warning"] == "Too large" for c in large_result["chunks"])


def test_chunk_preview_saves_debug_files(tmp_path: Path):
    text = "نمونه متن برای ذخیره."
    build_chunk_preview("save-id", text, tmp_path)

    folder = tmp_path / "save-id"
    assert (folder / "summary.json").exists()
    assert list(folder.glob("chunk_*.txt"))
