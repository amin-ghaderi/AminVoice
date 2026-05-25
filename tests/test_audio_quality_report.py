"""Tests for heuristic audio quality metrics."""

from __future__ import annotations

from backend.services.audio_quality_report import (
    _chunk_variation_score,
    _quality_label,
)


def test_chunk_variation_score():
    assert _chunk_variation_score([-20.0, -22.0, -19.0]) < 15
    assert _chunk_variation_score([-20.0, -35.0, -18.0]) > 30


def test_quality_label_good():
    assert _quality_label(0.05, 0, 4.0, 10.0) == "good"


def test_quality_label_needs_review():
    assert _quality_label(0.4, 5, 20.0, 50.0) == "needs_review"
