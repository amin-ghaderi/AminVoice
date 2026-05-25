"""Optional scene/style/tone prompt block for Gemini TTS (prompt-only, no pipeline change)."""

from __future__ import annotations


class SceneContext:
    def __init__(
        self,
        scene: str | None = None,
        style: str | None = None,
        tone: str | None = None,
    ):
        self.scene = scene
        self.style = style
        self.tone = tone

    def __repr__(self) -> str:
        return (
            f"SceneContext(scene={self.scene!r}, style={self.style!r}, "
            f"tone={self.tone!r}, enabled={self.is_enabled()})"
        )

    def is_enabled(self) -> bool:
        return bool(self.scene or self.style or self.tone)

    def build_prompt_block(self) -> str:
        if not self.is_enabled():
            return ""

        return f"""
## Scene Context (do NOT read aloud)
- Scene: {self.scene or "default narration environment"}
- Style: {self.style or "neutral audiobook style"}
- Tone: {self.tone or "consistent narration"}
""".strip()


def build_scene_context(
    *,
    use_scene: bool = False,
    scene: str | None = None,
    style: str | None = None,
    tone: str | None = None,
) -> SceneContext:
    """Build SceneContext from generation options; safe defaults when disabled."""
    if not use_scene:
        return SceneContext()
    return SceneContext(
        scene=scene if scene else None,
        style=style if style else None,
        tone=tone if tone else None,
    )
