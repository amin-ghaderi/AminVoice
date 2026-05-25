"""Final audiobook merge via FFmpeg CLI (no Python audio processing)."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

CHUNK_WAV_PATTERN = re.compile(r"^\d{4}\.wav$", re.IGNORECASE)

# EBU R128-ish target for loudnorm (optional second pass).
LOUDNORM_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"


class FFmpegNotFoundError(RuntimeError):
    """Raised when the ffmpeg executable is not on PATH."""


class FFmpegMergeError(RuntimeError):
    """Raised when ffmpeg exits with a non-zero status."""


def resolve_ffmpeg_executable() -> str:
    executable = shutil.which("ffmpeg")
    if not executable:
        logger.error("FFmpeg not installed")
        raise FFmpegNotFoundError(
            "FFmpeg not installed. Install ffmpeg and add it to your PATH, then retry."
        )
    return executable


def list_chunk_wavs(chunks_dir: Path) -> list[Path]:
    """Return chunk WAV paths sorted by numeric index (0001.wav, 0002.wav, …)."""
    if not chunks_dir.is_dir():
        raise FileNotFoundError(f"Chunks directory not found: {chunks_dir}")

    chunks = [
        path
        for path in chunks_dir.iterdir()
        if path.is_file() and CHUNK_WAV_PATTERN.match(path.name)
    ]
    chunks.sort(key=lambda path: path.name)
    return chunks


def _ffmpeg_safe_path(path: Path) -> str:
    """Path string safe for FFmpeg concat demuxer list entries."""
    resolved = path.resolve().as_posix()
    return resolved.replace("'", "'\\''")


def _write_concat_list(chunk_paths: list[Path], list_path: Path) -> None:
    lines = [f"file '{_ffmpeg_safe_path(chunk)}'" for chunk in chunk_paths]
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_ffmpeg(args: list[str], *, description: str) -> None:
    executable = resolve_ffmpeg_executable()
    command = [executable, *args]
    logger.info("FFmpeg %s: %s", description, " ".join(command))
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        logger.error("FFmpeg %s failed (code %s): %s", description, result.returncode, stderr)
        raise FFmpegMergeError(
            f"FFmpeg {description} failed (exit {result.returncode}): {stderr or 'no stderr'}"
        )


def merge_chunks_ffmpeg(
    intake_id: str,
    chunks_dir: str,
    output_path: str,
    *,
    apply_loudnorm: bool = True,
) -> Path:
    """
    Merge ordered chunk WAVs into one final audiobook using FFmpeg only.

    Original chunk files under chunks_dir are never deleted.
    """
    chunks_path = Path(chunks_dir)
    output = Path(output_path)
    chunk_paths = list_chunk_wavs(chunks_path)

    if not chunk_paths:
        raise ValueError(f"No chunk WAV files found in {chunks_path}")

    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"aminvoice-merge-{intake_id}-") as temp_dir:
        temp_root = Path(temp_dir)
        concat_list = temp_root / "list.txt"
        concat_output = temp_root / "concat.wav"

        _write_concat_list(chunk_paths, concat_list)
        _run_ffmpeg(
            [
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-c",
                "copy",
                str(concat_output),
            ],
            description="concat",
        )

        if not concat_output.exists() or concat_output.stat().st_size == 0:
            raise FFmpegMergeError("FFmpeg concat produced an empty output file")

        if apply_loudnorm:
            _run_ffmpeg(
                [
                    "-y",
                    "-i",
                    str(concat_output),
                    "-af",
                    LOUDNORM_FILTER,
                    "-c:a",
                    "pcm_s16le",
                    str(output),
                ],
                description="loudnorm",
            )
        else:
            shutil.copy2(concat_output, output)

    if not output.exists() or output.stat().st_size == 0:
        raise FFmpegMergeError(f"Final audiobook missing or empty: {output}")

    logger.info(
        "FFmpeg merge complete intake=%s chunks=%s output=%s bytes=%s",
        intake_id,
        len(chunk_paths),
        output,
        output.stat().st_size,
    )
    return output.resolve()
