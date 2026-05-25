"""Per-chunk Gemini TTS request/response debug persistence (observability only)."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

_CHUNK_STEM = re.compile(r"^(\d{4})$")


def infer_tts_debug_context(output_path: str) -> tuple[str | None, int | None]:
    """Derive intake_id and chunk index from .../audio/{intake_id}/0001.wav."""
    path = Path(output_path).resolve()
    chunk_index: int | None = None
    match = _CHUNK_STEM.match(path.stem)
    if match:
        chunk_index = int(match.group(1))
    intake_id = path.parent.name if path.parent.name else None
    return intake_id, chunk_index


def sanitize_config_snapshot(
    *,
    model: str,
    voice_name: str,
    temperature: float = 1,
) -> dict[str, Any]:
    """API config fields safe for debug files (no secrets)."""
    return {
        "model": model,
        "temperature": temperature,
        "voice_name": voice_name,
        "response_modalities": ["audio"],
        "speech_mode": "single_speaker",
    }


def scene_context_block(scene_context) -> str:
    if scene_context is None or not scene_context.is_enabled():
        return ""
    return (scene_context.build_prompt_block() or "").strip()


def build_request_payload(
    *,
    chunk_index: int | None,
    prompt: str,
    transcript: str,
    continuity_note: str | None,
    scene_block: str,
    token_name: str,
    attempt: int,
    config_snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "chunk_index": chunk_index,
        "prompt": prompt,
        "prompt_char_count": len(prompt),
        "config": config_snapshot,
        "continuity_note": (continuity_note or "").strip(),
        "scene_context": scene_block,
        "transcript": transcript,
        "transcript_char_count": len(transcript),
        "token_name": token_name,
        "attempt": attempt,
    }


def build_response_payload(
    *,
    success: bool,
    error: str | None = None,
    wav_path: str | None = None,
    wav_size_bytes: int | None = None,
    mime_type: str | None = None,
    audio_bytes: int | None = None,
    timestamp: float | None = None,
) -> dict[str, Any]:
    return {
        "success": success,
        "error": error,
        "wav_path": wav_path,
        "wav_size_bytes": wav_size_bytes,
        "mime_type": mime_type,
        "audio_bytes": audio_bytes,
        "timestamp": timestamp or time.time(),
    }


def persist_tts_debug_record(
    intake_id: str | None,
    chunk_index: int | None,
    record: dict[str, Any],
) -> None:
    """Write chunk JSON + update manifest; never raises to caller."""
    if not intake_id or chunk_index is None:
        logger.debug("TTS debug skip: missing intake_id or chunk_index")
        return

    try:
        base = get_settings().storage_root / "debug" / "tts" / intake_id
        base.mkdir(parents=True, exist_ok=True)

        chunk_path = base / f"chunk_{chunk_index:04d}.json"
        chunk_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        manifest_path = base / "manifest.json"
        manifest = _load_manifest(manifest_path)
        manifest["intake_id"] = intake_id
        manifest["updated_at"] = time.time()
        entries = [e for e in manifest.get("chunks", []) if e.get("chunk_index") != chunk_index]
        entries.append(record)
        entries.sort(key=lambda item: item.get("chunk_index") or 0)
        manifest["chunks"] = entries
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("TTS debug saved: %s", chunk_path)
    except OSError as exc:
        logger.warning("TTS debug persist failed (non-fatal): %s", exc)
    except Exception as exc:
        logger.warning("TTS debug persist failed (non-fatal): %s", exc)


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"chunks": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("chunks", [])
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"chunks": []}
