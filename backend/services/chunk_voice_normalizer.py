"""Pre-TTS chunk normalization for consistent tone and rhythm (meaning preserved)."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

MAX_WORDS_PER_SENTENCE = 40
MIN_WORDS_FRAGMENT = 6

_INVISIBLE = re.compile(r"[\u200c\u200d\u200e\u200f\u202a-\u202e\u2060\ufeff]")
_MULTI_SPACE = re.compile(r"[^\S\n]+")
_MULTI_DOTS = re.compile(r"\.{2,}")
_MULTI_ELLIPSIS = re.compile(r"…+")
_MULTI_BANG = re.compile(r"!{2,}")
_MULTI_QUESTION = re.compile(r"\?{2,}")
_MULTI_DASH = re.compile(r"—{2,}")

# Persian / Latin sentence boundaries (keep delimiter on left segment).
_SENTENCE_SPLIT = re.compile(
    r"(?<=[؟!؛.۔:…])\s+|(?<=[?!;])\s+"
)

# Prefer soft breaks inside oversized sentences.
_SOFT_BREAK_IN_WORD = re.compile(r"(،|؛|;|:)$")


def normalize_chunk_for_tts(text: str) -> str:
    """
    Normalize a single narration chunk before Gemini TTS.

    Structural edits only — no paraphrase, translation, or entity rewriting.
    """
    cleaned = text.strip()
    if not cleaned:
        return ""

    cleaned = _normalize_punctuation(cleaned)
    sentences = _split_sentences(cleaned)
    sentences = _expand_long_sentences(sentences)
    sentences = _merge_short_fragments(sentences)
    sentences = _stabilize_sentences(sentences)

    result = " ".join(sentences).strip()
    result = _normalize_punctuation(result)
    if result != text.strip():
        logger.debug(
            "Chunk voice normalizer applied (%s → %s chars)",
            len(text),
            len(result),
        )
    return result


def _normalize_punctuation(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _INVISIBLE.sub("", text)
    text = _MULTI_DOTS.sub(".", text)
    text = _MULTI_ELLIPSIS.sub("…", text)
    text = _MULTI_SPACE.sub(" ", text)

    # Persian comma spacing: no space before، single space after when followed by text.
    text = re.sub(r"\s+،", "،", text)
    text = re.sub(r"،(?=\S)", "، ", text)

    # Latin comma (OCR / mixed texts).
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r",(?=\S)", ", ", text)

    # Semicolon (Persian and Latin).
    text = re.sub(r"\s+؛", "؛", text)
    text = re.sub(r"؛(?=\S)", "؛ ", text)
    text = re.sub(r"\s+;", ";", text)
    text = re.sub(r";(?=\S)", "; ", text)

    # Collapse stray spaces before sentence punctuation.
    text = re.sub(r"\s+([.!?؟۔])", r"\1", text)
    return text.strip()


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split(text)
    return [part.strip() for part in parts if part.strip()]


def _word_count(sentence: str) -> int:
    return len(sentence.split())


def _expand_long_sentences(sentences: list[str]) -> list[str]:
    expanded: list[str] = []
    for sentence in sentences:
        expanded.extend(_break_long_sentence(sentence))
    return expanded


def _break_long_sentence(sentence: str, max_words: int = MAX_WORDS_PER_SENTENCE) -> list[str]:
    words = sentence.split()
    if len(words) <= max_words:
        return [sentence]

    parts: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        if end < len(words):
            floor = start + max(max_words // 2, 1)
            chosen = end
            for index in range(end - 1, floor - 1, -1):
                if _SOFT_BREAK_IN_WORD.search(words[index]):
                    chosen = index + 1
                    break
            end = chosen
        piece = " ".join(words[start:end]).strip()
        if piece:
            parts.append(piece)
        start = max(end, start + 1)

    return parts if parts else [sentence]


def _merge_short_fragments(
    sentences: list[str],
    min_words: int = MIN_WORDS_FRAGMENT,
) -> list[str]:
    if not sentences:
        return []

    merged: list[str] = []
    carry = ""

    for sentence in sentences:
        combined = f"{carry} {sentence}".strip() if carry else sentence
        if _word_count(combined) < min_words:
            carry = combined
            continue

        if carry:
            combined = f"{carry} {sentence}".strip()
            carry = ""
        merged.append(combined)

    if carry:
        if merged:
            merged[-1] = f"{merged[-1]} {carry}".strip()
        else:
            merged.append(carry)

    return merged


def _stabilize_sentences(sentences: list[str]) -> list[str]:
    """Reduce abrupt punctuation spikes (no wording changes)."""
    stabilized: list[str] = []
    for sentence in sentences:
        line = sentence.strip()
        line = _MULTI_BANG.sub("!", line)
        line = _MULTI_QUESTION.sub("؟", line)
        line = _MULTI_DOTS.sub(".", line)
        line = _MULTI_DASH.sub("—", line)
        stabilized.append(line)
    return stabilized
