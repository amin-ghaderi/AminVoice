"""Sequential chunk TTS + merge — MVP audiobook generation."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from backend.config.settings import Settings
from backend.services.ffmpeg_merger import FFmpegMergeError, FFmpegNotFoundError, merge_chunks_ffmpeg
from backend.services.audio_quality_report import AudioQualityReportStore, analyze_chunks
from backend.services.chunk_voice_normalizer import normalize_chunk_for_tts
from backend.services.voice_continuity import VoiceContinuityTracker
from backend.services.gemini_tts import TtsProgressHooks, generate_audio
from backend.services.scene_context import SceneContext
from backend.services.generation_status import GenerationStatus, GenerationStatusStore
from backend.services.text_splitter import split_text
from backend.services.token_config import load_enabled_tokens
from backend.services.token_pool import GenerationCancelled, TokenPool
from backend.services.token_pool_monitor import get_token_pool_monitor

logger = logging.getLogger(__name__)


def scan_completed_chunks(audio_dir: Path, total_chunks: int) -> tuple[int, list[Path]]:
    """
    Return the next chunk index to generate (1-based) and paths of existing wav files.

    Scans 0001.wav … sequentially; stops at the first gap.
    """
    completed: list[Path] = []
    for index in range(1, total_chunks + 1):
        path = audio_dir / f"{index:04d}.wav"
        if path.exists() and path.stat().st_size > 0:
            completed.append(path)
            continue
        return index, completed
    return total_chunks + 1, completed


class AudiobookGenerator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._status_store = GenerationStatusStore(settings.temp_dir / "generation")
        self._quality_store = AudioQualityReportStore(settings.temp_dir / "quality")
        self._tokens_file = settings.tokens_file

    @property
    def status_store(self) -> GenerationStatusStore:
        return self._status_store

    @property
    def quality_store(self) -> AudioQualityReportStore:
        return self._quality_store

    def run(
        self,
        intake_id: str,
        text: str,
        project_name: str,
        *,
        scene_context: SceneContext | None = None,
    ) -> None:
        audio_dir = self._settings.temp_dir / "audio" / intake_id
        audio_dir.mkdir(parents=True, exist_ok=True)
        output_dir = self._settings.outputs_dir / intake_id
        output_path = output_dir / "final_audiobook.wav"

        chunks = split_text(text)
        if not chunks:
            self._fail(intake_id, "No text to narrate.")
            return

        token_pool = TokenPool(self._tokens_file)
        monitor = get_token_pool_monitor()
        token_names = [entry["name"] for entry in load_enabled_tokens(self._tokens_file)]
        monitor.begin_run(intake_id, token_names, len(chunks))

        status = GenerationStatus(
            intake_id=intake_id,
            status="generating",
            status_label="Generating audiobook",
            total_chunks=len(chunks),
            total_tokens=token_pool.total,
            current_token_index=token_pool.current_index,
            eta="estimating...",
        )
        self._sync_token_fields(status, token_pool)
        self._status_store.write(status)

        start_index, chunk_paths = scan_completed_chunks(audio_dir, len(chunks))
        if start_index > 1:
            logger.info(
                "Resuming generation for %s at chunk %s/%s (%s already saved)",
                intake_id,
                start_index,
                len(chunks),
                len(chunk_paths),
            )
            status.current_chunk = len(chunk_paths)
            status.status_label = f"Resuming at chunk {start_index}/{len(chunks)}"
            self._status_store.write(status)

        continuity = VoiceContinuityTracker()
        if start_index > 1:
            continuity.seed_from_text(normalize_chunk_for_tts(chunks[start_index - 2]))

        scene_context = scene_context or SceneContext()
        logger.info("Scene mode: %s", scene_context.is_enabled())
        logger.info("Scene config: %s", scene_context)

        start_time = time.time()

        try:
            for index in range(start_index, len(chunks) + 1):
                if self._is_cancelled(intake_id):
                    status.status = "cancelled"
                    status.status_label = "Generation cancelled"
                    self._status_store.write(status)
                    logger.info("Generation cancelled: %s", intake_id)
                    monitor.end_run()
                    return

                chunk = chunks[index - 1]
                wav_path = audio_dir / f"{index:04d}.wav"

                status.status = "generating"
                status.status_label = "Generating audiobook"
                status.set_chunk_progress(index, chunk)
                self._sync_token_fields(status, token_pool)
                self._status_store.write(status)

                monitor.set_current_chunk(index)
                clean_text = normalize_chunk_for_tts(chunk)
                prepared = continuity.prepare_chunk(clean_text)
                ctx = prepared.voice_context
                logger.info(
                    "Generating chunk %s/%s (%s chars, continuity=%s punct=%s)",
                    index,
                    len(chunks),
                    len(prepared.transcript_text),
                    ctx.continuity_flag,
                    ctx.last_punctuation_type,
                )
                self._generate_chunk_with_retry(
                    intake_id,
                    index,
                    prepared.transcript_text,
                    prepared.conditioning_note,
                    wav_path,
                    token_pool,
                    status,
                    monitor,
                    scene_context=scene_context,
                )
                continuity.after_chunk(prepared.transcript_text)
                chunk_paths.append(wav_path)

                elapsed = time.time() - start_time
                done = len(chunk_paths)
                status.current_chunk = done
                status.progress_percent = round((done / len(chunks)) * 100, 1)
                self._sync_token_fields(status, token_pool)
                status.eta = self._estimate_eta(done, len(chunks), elapsed)
                self._status_store.write(status)

            status.status = "merging"
            status.status_label = "Merging final audio"
            status.eta = "merging..."
            self._status_store.write(status)
            logger.info("Merging %s chunks into final audiobook via FFmpeg", len(chunk_paths))

            merge_chunks_ffmpeg(intake_id, str(audio_dir), str(output_path))
            logger.info("Merged final audio: %s", output_path)

            try:
                report = analyze_chunks(chunk_paths, intake_id)
                self._quality_store.write(report)
            except Exception as exc:
                logger.warning("Audio quality report skipped for %s: %s", intake_id, exc)

        except GenerationCancelled:
            status.status = "cancelled"
            status.status_label = "Generation cancelled"
            self._status_store.write(status)
            logger.info("Generation cancelled: %s", intake_id)
            monitor.end_run()
            return
        except (FFmpegNotFoundError, FFmpegMergeError, Exception) as exc:
            monitor.end_run()
            self._fail(intake_id, str(exc))
            return

        monitor.end_run()
        status.status = "completed"
        status.status_label = "Audiobook ready"
        status.output_path = str(output_path)
        status.progress_percent = 100.0
        status.eta = "done"
        self._status_store.write(status)
        logger.info("Audiobook complete: %s", output_path)

    def _is_cancelled(self, intake_id: str) -> bool:
        current = self._status_store.read(intake_id)
        return bool(current and current.cancel_requested)

    def _generate_chunk_with_retry(
        self,
        intake_id: str,
        chunk_index: int,
        chunk: str,
        continuity_note: str,
        wav_path: Path,
        token_pool: TokenPool,
        status: GenerationStatus,
        monitor,
        *,
        scene_context: SceneContext | None = None,
        per_chunk_attempts: int = 5,
    ) -> None:
        hooks = TtsProgressHooks(
            cancel_checker=lambda: self._is_cancelled(intake_id),
            on_calling=lambda: self._set_status(
                status,
                status="generating",
                status_label="Calling Gemini",
            ),
            on_received=lambda: self._set_status(
                status,
                status="generating",
                status_label="Generating audiobook",
            ),
            on_rate_limited=lambda wait_s: self._set_status(
                status,
                status="waiting_quota",
                status_label=f"Waiting for Gemini quota reset (~{wait_s}s)",
                wait_seconds=wait_s,
                **self._token_status_kwargs(token_pool),
            ),
            on_waiting_tick=lambda remaining: self._set_status(
                status,
                status="waiting_quota",
                status_label=f"Waiting for Gemini quota reset (~{remaining}s)",
                wait_seconds=remaining,
                **self._token_status_kwargs(token_pool),
            ),
            on_token_used=lambda name: monitor.record_token_used(name, chunk_index),
            on_quota_exhausted=lambda name: monitor.record_quota_failure(name, chunk_index),
            on_token_switched=lambda from_n, to_n, reason: monitor.record_switch(
                from_n, to_n, reason, chunk_index
            ),
            on_pool_waiting=lambda wait_s: monitor.record_pool_waiting(wait_s),
            on_chunk_success=lambda name: monitor.record_chunk_success(name, chunk_index),
        )

        last_error: Exception | None = None
        for attempt in range(per_chunk_attempts):
            if self._is_cancelled(intake_id):
                raise GenerationCancelled("Cancelled before chunk retry.")
            try:
                generate_audio(
                    chunk,
                    str(wav_path),
                    token_pool,
                    max_attempts=12,
                    hooks=hooks,
                    continuity_note=continuity_note,
                    scene_context=scene_context,
                )
                self._sync_token_fields(status, token_pool)
                monitor.sync_active(token_pool.current_name(), token_pool.current_index)
                self._status_store.write(status)
                return
            except GenerationCancelled:
                raise
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Chunk %s failed (attempt %s/%s): %s",
                    wav_path.name,
                    attempt + 1,
                    per_chunk_attempts,
                    exc,
                )
                time.sleep(2)
        raise RuntimeError(f"Chunk {wav_path.name} failed after retries: {last_error}")

    def _set_status(self, record: GenerationStatus, **fields) -> None:
        for key, value in fields.items():
            setattr(record, key, value)
        self._status_store.write(record)

    @staticmethod
    def _token_status_kwargs(token_pool: TokenPool) -> dict:
        return {
            "current_token_index": token_pool.current_index,
            "current_token_name": token_pool.current_name() if token_pool.total else "",
            "quota_failovers": token_pool.quota_failovers,
        }

    @staticmethod
    def _sync_token_fields(status: GenerationStatus, token_pool: TokenPool) -> None:
        if token_pool.total:
            status.current_token_index = token_pool.current_index
            status.current_token_name = token_pool.current_name()
        status.quota_failovers = token_pool.quota_failovers

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
        status.status_label = "Generation failed"
        status.error = message
        self._status_store.write(status)
