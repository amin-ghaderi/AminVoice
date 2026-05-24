# To run this code you need to install the following dependencies:
# pip install google-genai
#
# Usage:
#   python api_limit_test.py

import mimetypes
import os
import struct
import time

from google import genai
from google.genai import types

MODEL = "gemini-3.1-flash-tts-preview"
REQUEST_COUNT = 20

# Fixed Persian audiobook sample (~45–60 seconds when narrated).
AUDIOBOOK_PROMPT = """Read the following Persian audiobook narration.

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

ما در آغاز متوجه نبودیم که انقلاب اسلامی، پدیده‌ای موقتی در تاریخ پُر تلاطم ایران نیست.

به بیان روشن‌تر،
نظامی که پدرم مظهر و نمایندهٔ آن بود،
در سال ۱۹۷۹ از میان رفت،
و هر نوع بازگشتی به گذشته،
نه امکان‌پذیر است
و نه مطلوب.

از سی سال پیش،
همهٔ تلاش و توانم را یکسره
در راه مبارزه با رژیم
و رهایی ایران به کار برده‌ام.

در پی مرگ پدرم،
شاه فقید ایران،
در ژوئیهٔ ۱۹۸۰،
به عنوان ولیعهد،
وارد عرصهٔ پیکار شدم.

در این سال‌ها،
هم با طرفداران نظام پادشاهی مشروطه همکاری کرده‌ام
و هم با جمهوری‌خواهان.

هم با نیروهای چپ
و هم با نیروهای راست.

در واقع،
فعالیتم را به عنوان مخالف حکومت اسلامی،
از هویت نهادی‌ام جدا کرده‌ام.

بی هیچ ابهامی،
خواستار یک قانون اساسی دمکراتیک عرفی برای ایران هستم،
که بر اعلامیهٔ جهانی حقوق بشر استوار شده باشد.
"""


def _iter_response_parts(response):
    """Yield parts from a generate_content response (handles layout variants)."""
    if response is None:
        return
    parts = getattr(response, "parts", None)
    if parts:
        for part in parts:
            yield part
        return
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if content is None:
            continue
        for part in getattr(content, "parts", None) or []:
            yield part


def _collect_inline_audio(response):
    """Collect inline audio parts from the response."""
    inline_items = []
    for part in _iter_response_parts(response):
        inline_data = getattr(part, "inline_data", None)
        if inline_data and getattr(inline_data, "data", None):
            inline_items.append(inline_data)
    return inline_items


def build_contents():
    return [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=AUDIOBOOK_PROMPT)],
        ),
    ]


def build_generate_content_config():
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


def parse_audio_mime_type(mime_type: str) -> dict[str, int | None]:
    bits_per_sample = 16
    rate = 24000

    parts = mime_type.split(";")
    for param in parts:
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


def audio_bytes_to_wav(response) -> bytes | None:
    inline_items = _collect_inline_audio(response)
    if not inline_items:
        return None

    mime_type = inline_items[0].mime_type or "audio/L16;rate=24000"
    combined_data = b"".join(item.data for item in inline_items if item.data)
    if not combined_data:
        return None

    if mimetypes.guess_extension(mime_type) != ".wav":
        return convert_to_wav(combined_data, mime_type)
    return combined_data


def save_wav(file_name: str, data: bytes) -> None:
    with open(file_name, "wb") as f:
        f.write(data)


def generate_one(client, contents, config, output_path: str) -> None:
    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=config,
    )
    if response is None:
        raise RuntimeError("Empty response from API.")

    wav_data = audio_bytes_to_wav(response)
    if wav_data is None:
        finish_reason = None
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish_reason = getattr(candidates[0], "finish_reason", None)
        detail = f" No audio in response."
        if finish_reason:
            detail += f" Finish reason: {finish_reason}"
        raise RuntimeError(detail.strip())

    save_wav(output_path, wav_data)


def run_limit_test():
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    contents = build_contents()
    config = build_generate_content_config()

    successful = 0
    failed = 0
    total_start = time.perf_counter()

    print(f"Starting API limit test: {REQUEST_COUNT} requests")
    print(f"Model: {MODEL}")
    print()

    for i in range(1, REQUEST_COUNT + 1):
        output_path = f"test_{i:03d}.wav"
        print(f"Request {i}/{REQUEST_COUNT}")

        request_start = time.perf_counter()
        try:
            generate_one(client, contents, config, output_path)
            elapsed = time.perf_counter() - request_start
            successful += 1
            print(f"Generation time: {elapsed:.2f} seconds")
            print(f"Saved: {output_path}")
        except Exception as exc:
            elapsed = time.perf_counter() - request_start
            failed += 1
            print(f"FAILED on request {i}")
            print(f"Error message: {exc}")
            print(f"Generation time: {elapsed:.2f} seconds")
        print()

    total_elapsed = time.perf_counter() - total_start
    total_minutes = total_elapsed / 60.0

    print("--- Summary ---")
    print(f"Successful requests: {successful}")
    print(f"Failed requests: {failed}")
    print(f"Total runtime: {total_minutes:.2f} minutes")


if __name__ == "__main__":
    run_limit_test()
