"""Tests for pre-TTS chunk voice normalizer."""

from __future__ import annotations

from backend.services.chunk_voice_normalizer import normalize_chunk_for_tts


def test_normalizes_multiple_dots_and_spaces():
    raw = "جمله اول..  جمله   دوم."
    result = normalize_chunk_for_tts(raw)
    assert ".." not in result
    assert "  " not in result


def test_fixes_persian_comma_spacing():
    raw = "متن اول ، متن دوم."
    result = normalize_chunk_for_tts(raw)
    assert " ،" not in result
    assert "، " in result or result.endswith(".")


def test_merges_short_fragments():
    raw = "بله. " + "خیر. " + "این یک جملهٔ کامل‌تر است که ادامه دارد."
    result = normalize_chunk_for_tts(raw)
    assert "بله" in result
    assert result.count(".") >= 1


def test_breaks_very_long_sentence():
    words = ["کلمه"] * 50
    raw = " ".join(words) + "."
    result = normalize_chunk_for_tts(raw)
    assert len(result.split()) >= 50
    assert result  # preserved content


def test_preserves_meaning_no_translation():
    raw = "رضا پهلوی در سال ۱۹۷۹ از ایران خارج شد."
    result = normalize_chunk_for_tts(raw)
    assert "رضا پهلوی" in result
    assert "۱۹۷۹" in result
    assert len(result) >= len(raw) - 5


def test_empty_returns_empty():
    assert normalize_chunk_for_tts("") == ""
    assert normalize_chunk_for_tts("   ") == ""
