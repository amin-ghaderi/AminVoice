"""Cross-chunk voice continuity metadata for smoother TTS (no chunking changes)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_SENTENCE_SPLIT = re.compile(
    r"(?<=[؟!؛.۔:…])\s+|(?<=[?!;])\s+"
)

_CONTINUATION_OPENERS = (
    "و ",
    "اما ",
    "ولی ",
    "که ",
    "چون ",
    "زیرا ",
    "اگر ",
    "چنانکه ",
    "همچنین ",
    "البته ",
)

_LEADING_CONNECTOR = re.compile(
    r"^(و|اما|ولی|که|چون|زیرا|اگر|چنانکه|همچنین|البته)\s+",
    re.IGNORECASE,
)


@dataclass
class VoiceContext:
    """Runtime continuity state passed between chunks."""

    last_sentence_end: str = ""
    last_punctuation_type: str = "none"
    continuity_flag: bool = False
    prior_sentences: str = ""

    def to_dict(self) -> dict:
        return {
            "last_sentence_end": self.last_sentence_end,
            "last_punctuation_type": self.last_punctuation_type,
            "continuity_flag": self.continuity_flag,
            "prior_sentences": self.prior_sentences,
        }


@dataclass
class PreparedChunk:
    """Chunk text for TTS transcript plus non-spoken conditioning."""

    transcript_text: str
    conditioning_note: str
    voice_context: VoiceContext


@dataclass
class VoiceContinuityTracker:
    """Builds per-chunk conditioning from the previous chunk only."""

    _context: VoiceContext = field(default_factory=VoiceContext)

    @property
    def context(self) -> VoiceContext:
        return self._context

    def seed_from_text(self, text: str) -> None:
        """Restore continuity after resume from an already-generated chunk."""
        self._context = _context_from_chunk(text)

    def prepare_chunk(self, normalized_chunk: str) -> PreparedChunk:
        conditioning = _build_conditioning_note(self._context)
        transcript = _adjust_chunk_opening(normalized_chunk, self._context)
        return PreparedChunk(
            transcript_text=transcript,
            conditioning_note=conditioning,
            voice_context=VoiceContext(
                last_sentence_end=self._context.last_sentence_end,
                last_punctuation_type=self._context.last_punctuation_type,
                continuity_flag=self._context.continuity_flag,
                prior_sentences=self._context.prior_sentences,
            ),
        )

    def after_chunk(self, spoken_chunk: str) -> VoiceContext:
        self._context = _context_from_chunk(spoken_chunk)
        logger.debug(
            "Voice continuity updated: punct=%s flag=%s tail=%r",
            self._context.last_punctuation_type,
            self._context.continuity_flag,
            self._context.last_sentence_end[:80] if self._context.last_sentence_end else "",
        )
        return self._context


def classify_end_punctuation(text: str) -> str:
    stripped = text.rstrip()
    if not stripped:
        return "none"
    if stripped.endswith(("،", ",")):
        return "comma"
    if stripped.endswith(("؟", "?")):
        return "question"
    if stripped.endswith("!"):
        return "exclamation"
    if stripped.endswith(("؛", ";")):
        return "semicolon"
    if stripped.endswith((".", "۔", "…")):
        return "period"
    return "other"


def extract_tail_sentences(text: str, count: int = 2) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return text.strip()
    return " ".join(sentences[-count:]).strip()


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split(text)
    return [part.strip() for part in parts if part.strip()]


def _context_from_chunk(text: str) -> VoiceContext:
    cleaned = text.strip()
    if not cleaned:
        return VoiceContext()

    last_sentence = _split_sentences(cleaned)[-1] if _split_sentences(cleaned) else cleaned
    punct = classify_end_punctuation(last_sentence)
    return VoiceContext(
        last_sentence_end=last_sentence,
        last_punctuation_type=punct,
        continuity_flag=punct in ("comma", "semicolon"),
        prior_sentences=extract_tail_sentences(cleaned, 2),
    )


def _build_conditioning_note(context: VoiceContext) -> str:
    if not context.prior_sentences:
        return (
            "This is the opening segment. "
            "Begin with a natural audiobook intro cadence."
        )

    lines = [
        "CONTINUITY REFERENCE — for pacing and tone only; do NOT read these lines aloud:",
        f"Previous ending ({context.last_punctuation_type}): "
        f"«{context.prior_sentences}»",
    ]

    if context.continuity_flag:
        lines.append(
            "The prior segment ended mid-thought (comma/semicolon). "
            "Continue the same breath and emotional line into the transcript below. "
            "Do not add a long pause at the start."
        )
    else:
        lines.append(
            "The prior segment ended on a full stop. "
            "Begin the transcript below with a gentle fresh beat while keeping the same narrator voice."
        )

    return "\n".join(lines)


def _adjust_chunk_opening(text: str, context: VoiceContext) -> str:
    """Light structural tweaks so the chunk does not start mid-thought."""
    adjusted = text.strip()
    if not adjusted:
        return adjusted

    adjusted = re.sub(r"^[،,]\s*", "", adjusted)

    if not context.prior_sentences:
        return adjusted

    sentences = _split_sentences(adjusted)
    if not sentences:
        return adjusted

    first = sentences[0]

    if context.continuity_flag:
        if _opens_mid_clause(first):
            sentences[0] = _soften_mid_clause_opening(first)
    elif context.last_punctuation_type == "period":
        if _orphan_continuation_after_stop(first):
            sentences[0] = _soften_fresh_segment_opening(first)

    return " ".join(sentences).strip()


def _opens_mid_clause(sentence: str) -> bool:
    """Chunk opens like the middle of a clause (not a named-entity headline)."""
    if sentence.startswith(_CONTINUATION_OPENERS):
        return False
    words = sentence.split()
    if len(words) >= 6:
        return False
    return bool(re.match(r"^[a-z0-9\"«(]", sentence))


def _orphan_continuation_after_stop(sentence: str) -> bool:
    return bool(_LEADING_CONNECTOR.match(sentence)) and len(sentence.split()) < 12


def _soften_mid_clause_opening(sentence: str) -> str:
    """Minimal connective prefix — same meaning, smoother handoff after comma."""
    if sentence.startswith("که "):
        return sentence
    return f"و {sentence}"


def _soften_fresh_segment_opening(sentence: str) -> str:
    """Drop a dangling conjunction right after a full-stop boundary."""
    return _LEADING_CONNECTOR.sub("", sentence, count=1).strip() or sentence
