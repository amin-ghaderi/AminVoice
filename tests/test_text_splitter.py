"""Tests for semantic text splitter."""

from __future__ import annotations

from backend.services.text_splitter import (
    DEFAULT_VALIDATION_MAX_CHARS,
    HARD_MAX_CHARS,
    VALIDATION_MAX_CHARS,
    VALIDATION_MIN_CHARS,
    compute_chunking_stats,
    resolve_validation_max_chars,
    split_text,
)


def test_splits_on_distinct_paragraphs_when_large_enough():
    # Each paragraph ~1200 chars; combined > SOFT_MAX — keep paragraph boundary.
    para_a = "پاراگراف اول. " + "جمله اضافی. " * 100
    para_b = "پاراگراف دوم. " + "ادامه متن. " * 100
    text = para_a + "\n\n" + para_b
    chunks = split_text(text)
    assert len(chunks) >= 2
    assert "پاراگراف اول" in chunks[0]
    assert "پاراگراف دوم" in chunks[-1]


def test_single_newlines_stay_together():
    text = "خط اول از پاراگراف\nخط دوم همان پاراگراف\nخط سوم همان پاراگراف."
    chunks = split_text(text)
    assert len(chunks) == 1
    assert "خط اول" in chunks[0]
    assert "خط سوم" in chunks[0]


def test_merges_micro_fragments():
    fragment_a = "شما پسر ارشد آخرین پادشاه ایران، محمد رضا شاه پهلوی، هستید."
    fragment_b = "رضا پهلوی در ادامه سخن می‌گوید."
    text = fragment_a + "\n\n" + fragment_b
    chunks = split_text(text)
    assert len(chunks) == 1


def test_strips_page_markers():
    text = "--- Page 4 ---\n\nمتن صفحه."
    chunks = split_text(text)
    assert chunks
    assert "Page" not in chunks[0]


def test_empty_returns_empty():
    assert split_text("") == []


def test_hard_max_not_exceeded():
    body = ("کلمه " * 400) + "پایان."
    chunks = split_text(body)
    for chunk in chunks:
        assert len(chunk) <= HARD_MAX_CHARS


def test_chunking_stats():
    chunks = split_text("جمله اول. " * 200 + "\n\n" + "جمله دوم. " * 200)
    stats = compute_chunking_stats(chunks)
    assert stats.total_chunks == len(chunks)
    assert stats.avg_chunk_length > 0


def test_legacy_max_chars_override():
    long = "بخش. " * 500
    chunks = split_text(long, max_chars=800)
    assert chunks
    assert max(len(c) for c in chunks) <= HARD_MAX_CHARS


def test_validation_no_empty_chunks():
    chunks = split_text("جمله اول. " * 50 + "\n\n" + "جمله دوم. " * 50)
    assert all(chunk.strip() for chunk in chunks)


def test_validation_splits_over_max_at_sentences():
    body = "بخش. " * 400
    chunks = split_text(body)
    assert all(len(c) <= VALIDATION_MAX_CHARS or "." in c for c in chunks)
    assert max(len(c) for c in chunks) <= VALIDATION_MAX_CHARS + 50


def test_validation_merges_tiny_middle_chunks():
    a = "جمله اول کامل. " * 25
    b = "کوتاه."
    c = "جمله سوم کامل. " * 25
    chunks = split_text(a + "\n\n" + b + "\n\n" + c)
    for chunk in chunks[:-1]:
        assert len(chunk) >= VALIDATION_MIN_CHARS or len(chunks) == 1


def test_validation_report_counts():
    chunks = split_text("جمله. " * 300)
    stats = compute_chunking_stats(chunks)
    assert stats.count_small_chunks == sum(1 for c in chunks if len(c) < VALIDATION_MIN_CHARS)
    assert stats.count_large_chunks == sum(1 for c in chunks if len(c) > VALIDATION_MAX_CHARS)


def test_resolve_validation_max_chars_clamps():
    assert resolve_validation_max_chars(None) == DEFAULT_VALIDATION_MAX_CHARS
    assert resolve_validation_max_chars(1000) == 1000
    assert resolve_validation_max_chars(500) == 600
    assert resolve_validation_max_chars(2000) == 1300


def test_validation_max_chars_produces_more_chunks():
    long = "جمله دوم. " * 400 + "\n\n" + "جمله سوم. " * 400
    small = split_text(long, validation_max_chars=600)
    large = split_text(long, validation_max_chars=1300)
    assert len(small) >= len(large)
    assert all(len(c) <= 650 for c in small)
