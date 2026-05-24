# To run this code you need to install the following dependencies:
# pip install google-genai

import mimetypes
import os
import re
import struct
from google import genai
from google.genai import types


def save_binary_file(file_name, data):
    f = open(file_name, "wb")
    f.write(data)
    f.close()
    print(f"File saved to to: {file_name}")


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
    """Collect inline audio parts and print any text parts."""
    inline_items = []
    for part in _iter_response_parts(response):
        inline_data = getattr(part, "inline_data", None)
        if inline_data and getattr(inline_data, "data", None):
            inline_items.append(inline_data)
            continue
        text = getattr(part, "text", None)
        if text:
            print(text)
    return inline_items


def generate():
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    model = "gemini-3.1-flash-tts-preview"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text="""Read the following Persian audiobook narration.

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

فصل اول
انتخاب دموکراتیک

میشل تبن: آقای رضا پهلوی! شما پسر ارشد آخرین پادشاه ایران، محمد رضا شاه پهلوی، هستید. نهاد پادشاهی ایران در آغاز سال ۱۹۷۹ با پیروزی انقلاب اسلامی و تسلط مذهبیون بنیادگرا به رهبری روح‌الله خمینی بر ایران، واژگون شد. هنگامی که در نشریات نخستین سال‌های دهه هشتاد میلادی می‌نگریم، از عمق خطای مفسران شگفت‌زده می‌شویم که در آن دوران، فروپاشی سریع رژیم خمینی را پیش‌بینی می‌کردند. با خواندن کتابی که کریستین مالار و آلن رودیه در سال ۱۹۸۶ درباره شما منتشر کردند، تصویر شاهزاده‌ای جوان و فعال را می‌یابیم که با شخصیت‌هایی که امروز در قید حیات نیستند و غالباً، مانند شاپور بختیار، به قتل رسیده‌اند، همراهی می‌شد. در آن زمان شما نسبتاً خوشبین به نظر می‌رسیدید و فکر می‌کردید که بتوانید به سرعت به ایران بازگردید اما، سی سال پس از انقلاب هم‌چنان شاهد ناگزیر افت فعالیت‌های مخالفان رژیم هستیم؛ چه روی داده است؟ در ارزیابی‌هایتان کجا دچار خطا شدید؟

رضا پهلوی: واقعیت آن است که رژیم اسلامی در نخستین سال استقرارش شکننده به نظر می‌رسید و مراکز قدرت و تصمیم‌گیری چندان هماهنگ نبودند. همانند بسیاری از هم‌میهنانم، من نیز توانایی و اراده رهبران رژیم انقلابی را در تأمین و تثبیت پایه‌های قدرت خویش، به هر بهایی که شده، دست‌کم گرفتم. هنوز از بازگشت خمینی به ایران در اول فوریه ۱۹۷۹ چیزی نگذشته بود که او سرکوبی ترسناک و بی‌رحمانه را، نه فقط علیه مخالفانش، علیه نیروهای سکولار، چپ و ملی‌گرایی که وی را به قدرت رسانده بودند، آغاز کرد.

ما در آغاز متوجه نبودیم که انقلاب اسلامی پدیده‌ای موقتی در تاریخ پر تلاطم ایران و پرانتز ساده‌ای که به سرعت بسته می‌شود، نیست. به بیان روشن‌تر، نظامی که پدرم مظهر و نماینده‌اش بود، در سال ۱۹۷۹ از میان رفت و هر نوع بازگشتی به گذشته نه امکان‌پذیر است و نه مطلوب.

از سی سال پیش همه تلاش و توانم را یکسره در راه مبارزه با رژیم و رهایی ایران به کار برده‌ام. در پی مرگ پدرم، شاه فقید ایران، در ژوئیه ۱۹۸۰، به عنوان ولیعهد، وارد عرصه پیکار شدم. در این سال‌ها هم با طرفداران نظام پادشاهی مشروطه همکاری کرده‌ام و هم با جمهوری‌خواهان، هم با نیروهای چپ و هم با نیروهای راست.

در واقع، فعالیتم را به عنوان مخالف حکومت اسلامی از هویت نهادی‌ام جدا کرده‌ام. بی‌هیچ ابهامی، خواستار یک قانون اساسی دموکراتیک عرفی برای ایران هستم که بر اعلامیه جهانی حقوق بشر استوار شده باشد. این رژیم دموکراتیک و عرفی می‌تواند دو شکل به خود بگیرد: اگر اکثریت مردم ایران یک حکومت پادشاهی مدرن و پارلمانی را برگزینند (نظیر آنچه که امروز در نروژ، سوئد، هلند، اسپانیا یا ژاپن می‌بینیم) از این انتخاب خرسند خواهم شد و این گزینه‌ای است که من نمایندگی می‌کنم. اما اگر ...
"""),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        response_modalities=[
            "audio",
        ],
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

    print("Generating audiobook...")

    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
    except Exception as exc:
        print(f"Error: API request failed: {exc}")
        return

    if response is None:
        print("Error: Empty response from API.")
        return

    inline_items = _collect_inline_audio(response)
    if not inline_items:
        print("Error: No audio data in response.")
        finish_reason = None
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish_reason = getattr(candidates[0], "finish_reason", None)
        if finish_reason:
            print(f"Finish reason: {finish_reason}")
        return

    mime_type = inline_items[0].mime_type or "audio/L16;rate=24000"
    combined_data = b"".join(item.data for item in inline_items if item.data)
    if not combined_data:
        print("Error: Audio parts were present but contained no data.")
        return

    data_buffer = combined_data
    file_extension = mimetypes.guess_extension(mime_type)
    if file_extension != ".wav":
        data_buffer = convert_to_wav(combined_data, mime_type)

    save_binary_file("output_full.wav", data_buffer)
    print("Audio generated successfully")
    print("Saved to output_full.wav")


def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Generates a WAV file header for the given audio data and parameters.

    Args:
        audio_data: The raw audio data as a bytes object.
        mime_type: Mime type of the audio data.

    Returns:
        A bytes object representing the WAV file header.
    """
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size  # 36 bytes for header fields before data chunk size

    # http://soundfile.sapp.org/doc/WaveFormat/

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",          # ChunkID
        chunk_size,       # ChunkSize (total file size - 8 bytes)
        b"WAVE",          # Format
        b"fmt ",          # Subchunk1ID
        16,               # Subchunk1Size (16 for PCM)
        1,                # AudioFormat (1 for PCM)
        num_channels,     # NumChannels
        sample_rate,      # SampleRate
        byte_rate,        # ByteRate
        block_align,      # BlockAlign
        bits_per_sample,  # BitsPerSample
        b"data",          # Subchunk2ID
        data_size         # Subchunk2Size (size of audio data)
    )
    return header + audio_data

def parse_audio_mime_type(mime_type: str) -> dict[str, int | None]:
    """Parses bits per sample and rate from an audio MIME type string.

    Assumes bits per sample is encoded like "L16" and rate as "rate=xxxxx".

    Args:
        mime_type: The audio MIME type string (e.g., "audio/L16;rate=24000").

    Returns:
        A dictionary with "bits_per_sample" and "rate" keys. Values will be
        integers if found, otherwise None.
    """
    bits_per_sample = 16
    rate = 24000

    # Extract rate from parameters
    parts = mime_type.split(";")
    for param in parts: # Skip the main type part
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate_str = param.split("=", 1)[1]
                rate = int(rate_str)
            except (ValueError, IndexError):
                # Handle cases like "rate=" with no value or non-integer value
                pass # Keep rate as default
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass # Keep bits_per_sample as default if conversion fails

    return {"bits_per_sample": bits_per_sample, "rate": rate}


if __name__ == "__main__":
    generate()

