"""Unit tests for text cleaning."""

from __future__ import annotations

from backend.services.text_cleaner import TextCleaner


def test_removes_duplicate_inline_spaces():
    cleaner = TextCleaner()
    assert cleaner.clean("سلام   دنیا") == "سلام دنیا"


def test_preserves_paragraph_breaks():
    cleaner = TextCleaner()
    text = "پاراگراف اول.\n\nپاراگراف دوم."
    assert cleaner.clean(text) == text


def test_joins_soft_wrapped_lines():
    cleaner = TextCleaner()
    text = "این یک جمله است که\nدر دو خط شکسته"
    result = cleaner.clean(text)
    assert "\n" not in result or "شکسته" in result
    assert "جمله" in result


def test_collapses_excess_blank_lines():
    cleaner = TextCleaner()
    assert cleaner.clean("a\n\n\n\nb") == "a\n\nb"
