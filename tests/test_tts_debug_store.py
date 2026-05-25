"""Tests for per-chunk TTS debug persistence."""

from __future__ import annotations

import json
from pathlib import Path

from backend.services.tts_debug_store import (
    build_request_payload,
    build_response_payload,
    infer_tts_debug_context,
    persist_tts_debug_record,
    sanitize_config_snapshot,
)


def test_infer_context_from_wav_path():
    intake_id, chunk_index = infer_tts_debug_context(
        r"C:\storage\temp\audio\job-abc\0003.wav"
    )
    assert intake_id == "job-abc"
    assert chunk_index == 3


def test_persist_chunk_and_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    from backend.config.settings import get_settings

    get_settings.cache_clear()
    get_settings()

    record = {
        "chunk_index": 1,
        "intake_id": "job-1",
        "request": build_request_payload(
            chunk_index=1,
            prompt="full prompt",
            transcript="transcript",
            continuity_note="note",
            scene_block="",
            token_name="token-a",
            attempt=1,
            config_snapshot=sanitize_config_snapshot(
                model="gemini-test",
                voice_name="Sulafat",
            ),
        ),
        "response": build_response_payload(
            success=True,
            wav_path=str(tmp_path / "0001.wav"),
            wav_size_bytes=1000,
        ),
    }
    persist_tts_debug_record("job-1", 1, record)

    chunk_file = tmp_path / "storage" / "debug" / "tts" / "job-1" / "chunk_0001.json"
    manifest_file = tmp_path / "storage" / "debug" / "tts" / "job-1" / "manifest.json"
    assert chunk_file.exists()
    data = json.loads(chunk_file.read_text(encoding="utf-8"))
    assert data["request"]["prompt"] == "full prompt"
    assert data["response"]["success"] is True
    assert "api_key" not in chunk_file.read_text(encoding="utf-8").lower()

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert len(manifest["chunks"]) == 1
