"""Unit tests for Persian text repair."""

from __future__ import annotations

from pathlib import Path

from backend.services.persian_text_repair import PersianTextRepairService


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
    assert "۱۹۷۹" in result.text or "1979" in result.text
    assert any(c.kind == "DIGIT_REPAIR" for c in result.changes)


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
