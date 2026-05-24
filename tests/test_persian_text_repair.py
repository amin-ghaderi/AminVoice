"""Unit tests for Persian text repair."""

from __future__ import annotations

from pathlib import Path

from backend.services.persian_text_repair import (
    PersianTextRepairService,
    repair_persian_years,
    repair_persian_years_with_changes,
)


def test_glyph_replacement_islamic():
    service = PersianTextRepairService()
    result = service.repair("رژيم اس)می در نخستين سال")
    assert "اسلامی" in result.text
    assert "اس)می" not in result.text
    assert any(c.kind == "REPLACED" for c in result.changes)


def test_join_broken_persian_word():
    service = PersianTextRepairService()
    text = "انتخاب دموکر\nاتيک\n\nپاراگراف بعدی."
    result = service.repair(text)
    assert "دموکراتيک" in result.text or "دموکراتیک" in result.text
    assert any(c.kind == "JOINED_LINE" for c in result.changes)


def test_join_paragraph_lines():
    service = PersianTextRepairService()
    text = "ما در آغاز\nمتوجه نبودیم\n\nفصل بعد."
    result = service.repair(text)
    assert "ما در آغاز متوجه نبودیم" in result.text
    assert "\n\nفصل بعد." in result.text or result.text.endswith("فصل بعد.")


def test_digit_year_repair():
    service = PersianTextRepairService()
    text = "در سال\n٩٧٩١\n\nبا پيروزی"
    result = service.repair(text)
    assert "۱۹۷۹" in result.text
    assert any(c.kind == "YEAR_FIX" for c in result.changes)


def test_reversed_persian_year():
    assert repair_persian_years("انقلاب ٩٧٩١ میلادی") == "انقلاب ۱۹۷۹ میلادی"


def test_arabic_digit_year_1980():
    assert repair_persian_years("ژوئيه ٠٨٩١") == "ژوئيه ۱۹۸۰"


def test_arabic_digit_year_1986():
    assert repair_persian_years("سال ٦٨٩١") == "سال ۱۹۸۶"


def test_arabic_digit_year_1989():
    assert repair_persian_years("سال ٩٨٩١") == "سال ۱۹۸۹"


def test_mixed_digit_year():
    text = repair_persian_years("در 19۸9")
    assert "۱۹۸۹" in text


def test_invalid_numbers_untouched():
    assert repair_persian_years("صفحه ١١ و ١٢۳۴") == "صفحه ١١ و ١٢۳۴"
    assert repair_persian_years("نرخ 25 درصد") == "نرخ 25 درصد"
    assert repair_persian_years("قیمت 1234567") == "قیمت 1234567"


def test_normal_year_unchanged():
    assert repair_persian_years("در سال ۱۹۷۹") == "در سال ۱۹۷۹"


def test_year_fix_diagnostics_format():
    _, changes = repair_persian_years_with_changes("سال ٩٧٩١")
    assert changes
    assert changes[0].to_diff_block().startswith("[YEAR_FIX]")
    assert "٩٧٩١" in changes[0].before
    assert "۱۹۷۹" in changes[0].after


def test_english_text_mostly_unchanged():
    service = PersianTextRepairService()
    original = "Hello world.\n\nThis is a test paragraph."
    result = service.repair(original)
    assert result.text == original
    assert result.fix_count == 0


def test_save_diagnostics(tmp_path: Path):
    service = PersianTextRepairService(debug_dir=tmp_path)
    before = "رژيم اس)می"
    result = service.repair(before)
    out = service.save_diagnostics("test-id", before, result)
    assert out is not None
    assert (out / "before_repair.txt").exists()
    assert (out / "after_repair.txt").exists()
    assert (out / "repair_diff.txt").read_text(encoding="utf-8")


def test_khomeini_glyph_pattern():
    service = PersianTextRepairService()
    result = service.repair("رھبری روح 0 خمينی برايران")
    assert "روح الله خمینی" in result.text
