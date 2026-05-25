"""Tests for optional scene prompt injection."""

from backend.services.gemini_tts import _build_tts_prompt
from backend.services.scene_context import SceneContext, build_scene_context


def test_scene_context_disabled_by_default():
    ctx = SceneContext()
    assert ctx.is_enabled() is False
    assert ctx.build_prompt_block() == ""


def test_scene_context_builds_block_when_set():
    ctx = SceneContext(scene="library", style="warm", tone="reflective")
    block = ctx.build_prompt_block()
    assert "## Scene Context" in block
    assert "library" in block
    assert "warm" in block
    assert "reflective" in block


def test_build_tts_prompt_unchanged_without_scene():
    base = _build_tts_prompt("سلام", continuity_note="keep pace")
    with_scene = _build_tts_prompt("سلام", continuity_note="keep pace", scene_context=SceneContext())
    assert base == with_scene


def test_build_scene_context_respects_use_scene_flag():
    off = build_scene_context(use_scene=False, scene="x", style="documentary", tone="calm")
    assert off.is_enabled() is False
    on = build_scene_context(use_scene=True, style="documentary", tone="calm")
    assert on.is_enabled() is True
    assert on.style == "documentary"
    assert on.scene is None


def test_build_tts_prompt_injects_scene_before_transcript():
    ctx = SceneContext(scene="studio")
    prompt = _build_tts_prompt("متن", scene_context=ctx)
    scene_pos = prompt.index("## Scene Context")
    transcript_pos = prompt.rindex("متن")
    continuity_marker = "## Voice continuity"
    assert scene_pos < transcript_pos
    if continuity_marker in prompt:
        assert prompt.index(continuity_marker) < scene_pos
