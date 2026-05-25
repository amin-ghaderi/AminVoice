"""Tests for cross-chunk voice continuity."""

from __future__ import annotations

from backend.services.voice_continuity import (
    VoiceContinuityTracker,
    VoiceContext,
    classify_end_punctuation,
    extract_tail_sentences,
)


def test_classify_comma_and_period():
    assert classify_end_punctuation("ادامه مطلب،") == "comma"
    assert classify_end_punctuation("پایان.") == "period"


def test_continuity_flag_follows_punctuation():
    tracker = VoiceContinuityTracker()
    tracker.after_chunk("جمله اول، جمله دوم،")
    assert tracker.context.continuity_flag is True
    assert tracker.context.last_punctuation_type == "comma"

    tracker.after_chunk("بخش جدید.")
    assert tracker.context.continuity_flag is False
    assert tracker.context.last_punctuation_type == "period"


def test_prepare_includes_prior_sentences_in_conditioning_not_transcript():
    tracker = VoiceContinuityTracker()
    tracker.after_chunk("پاراگراف قبل. جمله پایانی،")

    prepared = tracker.prepare_chunk("شروع بخش تازه در اینجا ادامه می‌یابد.")
    assert "do NOT read" in prepared.conditioning_note.lower() or "NOT read" in prepared.conditioning_note
    assert tracker.context.prior_sentences in prepared.conditioning_note
    assert tracker.context.prior_sentences not in prepared.transcript_text


def test_extract_tail_sentences():
    text = "اول. دوم. سوم. چهارم."
    tail = extract_tail_sentences(text, 2)
    assert "سوم" in tail
    assert "چهارم" in tail
    assert "اول" not in tail


def test_voice_context_to_dict():
    ctx = VoiceContext(
        last_sentence_end="پایان،",
        last_punctuation_type="comma",
        continuity_flag=True,
        prior_sentences="قبلی،",
    )
    data = ctx.to_dict()
    assert data["continuity_flag"] is True
    assert data["last_punctuation_type"] == "comma"
