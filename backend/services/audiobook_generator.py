"""Sequential chunk TTS + merge — MVP audiobook generation."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from backend.config.settings import Settings
from backend.services.audio_merger import merge_wav_files
from backend.services.gemini_tts import generate_audio
from backend.services.generation_status import GenerationStatus, GenerationStatusStore
from backend.services.text_splitter import split_text
from backend.services.token_pool import TokenPool

logger = logging.getLogger(__name__)


class AudiobookGenerator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._status_store = GenerationStatusStore(settings.temp_dir / "generation")
        self._tokens_file = settings.tokens_file

    @property
    def status_store(self) -> GenerationStatusStore:
        return self._status_store

    def run(self, intake_id: str, text: str, project_name: str) -> None:
        audio_dir = self._settings.temp_dir / "audio" / intake_id
        audio_dir.mkdir(parents=True, exist_ok=True)

        chunks = split_text(text)
        if not chunks:
            self._fail(intake_id, "No text to narrate.")
            return

        token_pool = TokenPool(self._tokens_file)
        status = GenerationStatus(
            intake_id=intake_id,
            status="generating",
            total_chunks=len(chunks),
            total_tokens=token_pool.total,
            current_token_index=token_pool.current_index,
            eta="estimating...",
        )
        self._status_store.write(status)

        chunk_paths: list[Path] = []
        start_time = time.time()

        for index, chunk in enumerate(chunks, start=1):
            current = self._status_store.read(intake_id)
            if current and current.cancel_requested:
                status.status = "cancelled"
                self._status_store.write(status)
                logger.info("Generation cancelled: %s", intake_id)
                return

            wav_path = audio_dir / f"{index:04d}.wav"
            self._generate_chunk_with_retry(chunk, wav_path, token_pool)
            chunk_paths.append(wav_path)

            elapsed = time.time() - start_time
            status.current_chunk = index
            status.current_token_index = token_pool.current_index
            status.eta = self._estimate_eta(index, len(chunks), elapsed)
            self._status_store.write(status)

        output_path = self._settings.outputs_dir / f"{intake_id}_final_audiobook.wav"
        try:
            merge_wav_files(chunk_paths, output_path)
        except Exception as exc:
            self._fail(intake_id, f"Merge failed: {exc}")
            return

        status.status = "completed"
        status.output_path = str(output_path)
        status.eta = "done"
        self._status_store.write(status)
        logger.info("Audiobook complete: %s", output_path)

    def _generate_chunk_with_retry(
        self,
        chunk: str,
        wav_path: Path,
        token_pool: TokenPool,
        *,
        per_chunk_attempts: int = 5,
    ) -> None:
        last_error: Exception | None = None
        for _ in range(per_chunk_attempts):
            try:
                generate_audio(
                    chunk,
                    str(wav_path),
                    token_pool,
                    max_attempts=12,
                )
                return
            except Exception as exc:
                last_error = exc
                logger.warning("Chunk failed (%s), retrying: %s", wav_path.name, exc)
                time.sleep(2)
        raise RuntimeError(f"Chunk failed after retries: {last_error}")

    def _estimate_eta(self, done: int, total: int, elapsed: float) -> str:
        if done <= 0:
            return "estimating..."
        remaining = total - done
        per_chunk = elapsed / done
        seconds = int(remaining * per_chunk)
        if seconds < 60:
            return f"~{seconds}s"
        return f"~{seconds // 60}m {seconds % 60}s"

    def _fail(self, intake_id: str, message: str) -> None:
        logger.error("Generation failed for %s: %s", intake_id, message)
        status = self._status_store.read(intake_id) or GenerationStatus(intake_id=intake_id)
        status.status = "failed"
        status.error = message
        self._status_store.write(status)
