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

این رژیم دمکراتیک و عرفی
می‌تواند دو شکل به خود بگیرد:

اگر اکثریت مردم ایران
یک حکومت پادشاهی مدرن و پارلمانی را برگزینند،
نظیر آنچه که امروز
در نروژ،
سوئد،
هلند،
اسپانیا
یا ژاپن می‌بینیم،

از این انتخاب خرسند خواهم شد.

و این گزینه‌ای است
که من نمایندگی می‌کنم.

اما اگر
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

    file_index = 0
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        if (
            chunk.parts is None
        ):
            continue
        if chunk.parts[0].inline_data and chunk.parts[0].inline_data.data:
            file_name = f"ENTER_FILE_NAME_{file_index}"
            file_index += 1
            inline_data = chunk.parts[0].inline_data
            data_buffer = inline_data.data
            file_extension = mimetypes.guess_extension(inline_data.mime_type)
            if file_extension is None:
                file_extension = ".wav"
                data_buffer = convert_to_wav(inline_data.data, inline_data.mime_type)
            save_binary_file(f"{file_name}{file_extension}", data_buffer)
        else:
            if text := chunk.text:
                print(text)

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


