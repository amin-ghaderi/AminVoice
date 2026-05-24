"""Gemini non-streaming TTS (migrated from prototypes/ai_studio_nonstream.py)."""

from __future__ import annotations

import logging
import mimetypes
import struct
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from google import genai
from google.genai import types

from backend.services.token_pool import GenerationCancelled, TokenPool

logger = logging.getLogger(__name__)

MODEL = "gemini-3.1-flash-tts-preview"

_DIRECTOR_PROMPT = """Read the following Persian audiobook narration.

# Director's note

Style:
Warm, emotionally engaging, cinematic, deeply human.

Voice:
Warm masculine Persian narrator.
Deep but soft voice.
Professional audiobook quality.
Natural Persian pronunciation.

Pacing:
Natural pacing.
Not too slow.
Not robotic.
Smooth storytelling rhythm.

Emotion:
Warm, reflective, emotionally engaging.
Speak naturally like a premium Persian audiobook narrator telling an important life story.

Avoid:
Monotone voice.
Cold documentary tone.
Excessive slowness.
Overly dramatic acting.

## Sample Context:
A premium Persian audiobook narrator telling an important life story in a warm, emotionally engaging, cinematic way. Natural pacing, warm emotional depth, human sounding voice.

## Transcript:

Speaker 1:
[speak warmly]
[natural pacing]
[cinematic]
[human tone]

"""


@dataclass
class TtsProgressHooks:
    on_calling: Callable[[], None] | None = None
    on_received: Callable[[], None] | None = None
    on_rate_limited: Callable[[int], None] | None = None
    on_waiting_tick: Callable[[int], None] | None = None
    cancel_checker: Callable[[], bool] | None = None


def _build_generate_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        temperature=1,
        response_modalities=["audio"],
        speech_config=types.SpeechConfig(
            multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                speaker_voice_configs=[
                    types.SpeakerVoiceConfig(
                        speaker="Speaker 1",
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name="Sulafat"
                            )
                        ),
                    ),
                    types.SpeakerVoiceConfig(
                        speaker="Speaker 2",
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name="Puck"
                            )
                        ),
                    ),
                ]
            ),
        ),
    )


def _iter_response_parts(response):
    if response is None:
        return
    parts = getattr(response, "parts", None)
    if parts:
        for part in parts:
            yield part
        return
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        if content is None:
            continue
        for part in getattr(content, "parts", None) or []:
            yield part


def _collect_inline_audio(response) -> list:
    items = []
    for part in _iter_response_parts(response):
        inline_data = getattr(part, "inline_data", None)
        if inline_data and getattr(inline_data, "data", None):
            items.append(inline_data)
    return items


def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + audio_data


def parse_audio_mime_type(mime_type: str) -> dict[str, int]:
    bits_per_sample = 16
    rate = 24000
    for param in mime_type.split(";"):
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate = int(param.split("=", 1)[1])
            except (ValueError, IndexError):
                pass
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass
    return {"bits_per_sample": bits_per_sample, "rate": rate}


def _is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc).upper()
    return "429" in message or "RESOURCE_EXHAUSTED" in message


def generate_audio(
    text: str,
    output_path: str,
    token_pool: TokenPool,
    *,
    max_attempts: int = 15,
    hooks: TtsProgressHooks | None = None,
) -> None:
    """Generate one WAV file for a text chunk with token fallback on quota errors."""
    prompt = _DIRECTOR_PROMPT + text.strip()
    config = _build_generate_config()
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        )
    ]

    last_error: Exception | None = None
    tried_all_tokens = False
    cancel_checker = hooks.cancel_checker if hooks else None

    for attempt in range(max_attempts):
        if cancel_checker and cancel_checker():
            raise GenerationCancelled("Generation cancelled.")

        api_key = token_pool.current_key()
        client = genai.Client(api_key=api_key)
        try:
            if hooks and hooks.on_calling:
                hooks.on_calling()
            logger.info("Calling Gemini TTS (token %s/%s)", token_pool.current_index, token_pool.total)

            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=config,
            )

            if hooks and hooks.on_received:
                hooks.on_received()
            logger.info("Gemini response received")

            inline_items = _collect_inline_audio(response)
            if not inline_items:
                raise RuntimeError("No audio data in Gemini response.")

            mime_type = inline_items[0].mime_type or "audio/L16;rate=24000"
            combined = b"".join(item.data for item in inline_items if item.data)
            if not combined:
                raise RuntimeError("Audio response was empty.")

            data_buffer = combined
            if mimetypes.guess_extension(mime_type) != ".wav":
                data_buffer = convert_to_wav(combined, mime_type)

            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data_buffer)
            logger.info("Saved wav: %s", out.name)
            return

        except GenerationCancelled:
            raise
        except Exception as exc:
            last_error = exc
            if _is_rate_limit_error(exc):
                if hooks and hooks.on_rate_limited:
                    hooks.on_rate_limited(token_pool.wait_seconds)
                if not token_pool.advance():
                    token_pool.wait_and_reset(
                        cancel_checker=cancel_checker,
                        on_tick=hooks.on_waiting_tick if hooks else None,
                    )
                    tried_all_tokens = True
                continue

            if attempt < max_attempts - 1:
                time.sleep(2)
                continue
            raise

    detail = f"after {max_attempts} attempts"
    if tried_all_tokens:
        detail += " (all tokens exhausted)"
    raise RuntimeError(f"TTS generation failed {detail}: {last_error}")
