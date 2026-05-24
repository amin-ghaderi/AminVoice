"""Tests for semantic text splitter."""

from __future__ import annotations

from backend.services.text_splitter import (
    HARD_MAX_CHARS,
    SOFT_MIN_CHARS,
    SOFT_MAX_CHARS,
    compute_chunking_stats,
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
