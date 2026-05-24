"""Conservative Persian text repair after PDF extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Known PDF glyph / encoding corruption patterns (longest keys first at apply time).
DEFAULT_GLYPH_REPLACEMENTS: dict[str, str] = {
    "روح 0 خمينی": "روح الله خمینی",
    "روح 0 خمینی": "روح الله خمینی",
    "اس)می": "اسلامی",
    "اس-می": "اسلامی",
    "انق)ب": "انقلاب",
    "انق-ب": "انقلاب",
    "انق)بی": "انقلابی",
    "جمھوری": "جمهوری",
    "مي-دی": "دهه‌ی هشتاد",
    "ما=ر": "مارک",
    "ت)طم": "تلاطم",
    "ت)ش": "تلاش",
    "اع)م": "اعلام",
    "عُرفی": "عرفی",
}

_PERSIAN_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")
_SENTENCE_END = re.compile(r"[.!?؟۔:\]\)»\"']\s*$")
_DIGITS_CLASS = r"۰-۹0-9٠-٩"
_DIGIT_CHAR = re.compile(f"[{_DIGITS_CLASS}]")
_LATIN_WORD = re.compile(r"[A-Za-z]{4,}")

# Do not apply single-char ھ→ه globally via dict; handle separately if needed.
_GLYPH_REPLACEMENTS_SAFE = {
    k: v for k, v in DEFAULT_GLYPH_REPLACEMENTS.items() if len(k) > 2
}

_GREGORIAN_YEAR_MIN = 1900
_GREGORIAN_YEAR_MAX = 2099

# Standalone exactly-four-digit tokens (Persian, Arabic, or Western digits).
_YEAR_TOKEN = re.compile(rf"(?<![{_DIGITS_CLASS}])([{_DIGITS_CLASS}]{{4}})(?![{_DIGITS_CLASS}])")


@dataclass
class RepairChange:
    kind: str
    before: str
    after: str

    def to_diff_block(self) -> str:
        if self.kind == "JOINED_LINE":
            return f"[JOINED_LINE]\n{self.before}\n→ {self.after}"
        if self.kind == "JOINED_PARAGRAPH":
            return f"[JOINED_PARAGRAPH]\n{self.before}\n→ {self.after}"
        if self.kind == "DIGIT_REPAIR":
            return f"[DIGIT_REPAIR]\n{self.before}\n→ {self.after}"
        if self.kind == "YEAR_FIX":
            return f"[YEAR_FIX]\n{self.before}\n→ {self.after}"
        return f"[REPLACED]\n{self.before}\n→ {self.after}"


@dataclass
class RepairResult:
    text: str
    changes: list[RepairChange] = field(default_factory=list)

    @property
    def fix_count(self) -> int:
        return len(self.changes)


class PersianTextRepairService:
    """Rule-based repair pipeline for Persian PDF extraction artifacts."""

    def __init__(
        self,
        glyph_replacements: dict[str, str] | None = None,
        debug_dir: Path | None = None,
    ) -> None:
        self._glyph_map = dict(glyph_replacements or _GLYPH_REPLACEMENTS_SAFE)
        self._glyph_keys = sorted(self._glyph_map.keys(), key=len, reverse=True)
        self._debug_dir = debug_dir

    def repair(self, text: str) -> RepairResult:
        if not text or not text.strip():
            return RepairResult(text=text or "")

        changes: list[RepairChange] = []
        current = text.replace("\r\n", "\n").replace("\r", "\n")

        current, glyph_changes = self._apply_glyph_replacements(current)
        changes.extend(glyph_changes)

        current, year_changes = repair_persian_years_with_changes(current)
        changes.extend(year_changes)

        current, line_changes = self._repair_broken_lines(current)
        changes.extend(line_changes)

        current, para_changes = self._normalize_paragraphs(current)
        changes.extend(para_changes)

        return RepairResult(text=current, changes=changes)

    def save_diagnostics(
        self,
        intake_id: str,
        before: str,
        result: RepairResult,
    ) -> Path | None:
        if self._debug_dir is None:
            return None

        target = self._debug_dir / intake_id
        target.mkdir(parents=True, exist_ok=True)

        (target / "before_repair.txt").write_text(before, encoding="utf-8")
        (target / "after_repair.txt").write_text(result.text, encoding="utf-8")

        diff_body = "\n\n".join(c.to_diff_block() for c in result.changes)
        if not diff_body:
            diff_body = "(no changes applied)"
        (target / "repair_diff.txt").write_text(diff_body, encoding="utf-8")
        return target

    def _apply_glyph_replacements(self, text: str) -> tuple[str, list[RepairChange]]:
        changes: list[RepairChange] = []
        for key in self._glyph_keys:
            if key not in text:
                continue
            replacement = self._glyph_map[key]
            count = text.count(key)
            text = text.replace(key, replacement)
            changes.append(
                RepairChange(
                    kind="REPLACED",
                    before=key,
                    after=replacement if count == 1 else f"{replacement} (×{count})",
                )
            )
        return text, changes

    def _repair_broken_lines(self, text: str) -> tuple[str, list[RepairChange]]:
        lines = text.split("\n")
        changes: list[RepairChange] = []
        merged: list[str] = []
        i = 0

        while i < len(lines):
            current = lines[i]
            if i + 1 < len(lines) and self._should_join_broken_word(current, lines[i + 1]):
                nxt = lines[i + 1]
                joined = self._join_broken_word_lines(current, nxt)
                changes.append(
                    RepairChange(
                        kind="JOINED_LINE",
                        before=f"{current.strip()} + {nxt.strip()}",
                        after=joined.strip(),
                    )
                )
                merged.append(joined)
                i += 2
                continue
            merged.append(current)
            i += 1

        return "\n".join(merged), changes

    def _normalize_paragraphs(self, text: str) -> tuple[str, list[RepairChange]]:
        paragraphs = re.split(r"\n\s*\n", text)
        changes: list[RepairChange] = []
        normalized: list[str] = []

        for para in paragraphs:
            lines = [ln.strip() for ln in para.split("\n") if ln.strip()]
            if not lines:
                normalized.append("")
                continue
            if len(lines) == 1:
                normalized.append(lines[0])
                continue

            joined_parts: list[str] = [lines[0]]
            for idx in range(1, len(lines)):
                prev = joined_parts[-1]
                cur = lines[idx]
                if self._should_join_paragraph_line(prev, cur):
                    combined = f"{prev} {cur}"
                    changes.append(
                        RepairChange(
                            kind="JOINED_PARAGRAPH",
                            before=f"{prev} | {cur}",
                            after=combined,
                        )
                    )
                    joined_parts[-1] = combined
                else:
                    joined_parts.append(cur)

            normalized.append("\n".join(joined_parts))

        return "\n\n".join(normalized).strip(), changes

    def _should_join_broken_word(self, upper: str, lower: str) -> bool:
        u = upper.strip()
        low = lower.strip()
        if not u or not low:
            return False
        if _SENTENCE_END.search(u):
            return False
        if low.startswith(("-", "•", "*", "#", "---")):
            return False
        if u.startswith("--- Page"):
            return False
        if " " in low:
            return False
        if _DIGIT_CHAR.fullmatch(low.replace(" ", "")):
            return False
        if _DIGIT_CHAR.fullmatch(u.split()[-1].replace(" ", "")):
            return False
        if not self._is_persian_heavy(u) or not self._is_persian_heavy(low):
            return False
        if len(low) > 24:
            return False
        last_token = u.split()[-1]
        if len(last_token) > 32:
            return False
        return self._ends_with_letter(last_token) and self._starts_with_letter(low)

    def _join_broken_word_lines(self, upper: str, lower: str) -> str:
        u = upper.rstrip()
        low = lower.lstrip()
        parts = u.split()
        if len(parts) > 1:
            prefix = " ".join(parts[:-1])
            combined_word = parts[-1] + low
            return f"{prefix} {combined_word}"
        return u + low

    def _should_join_paragraph_line(self, prev: str, cur: str) -> bool:
        if _SENTENCE_END.search(prev):
            return False
        if cur.startswith(("-", "•", "*", "#")):
            return False
        if not self._is_persian_heavy(prev) or not self._is_persian_heavy(cur):
            return False
        if len(prev) > 120 or len(cur) > 120:
            return False
        return True

    @staticmethod
    def _is_persian_heavy(text: str) -> bool:
        letters = [c for c in text if c.isalpha() or _PERSIAN_RE.match(c)]
        if not letters:
            return False
        persian = sum(1 for c in letters if _PERSIAN_RE.match(c))
        return persian / len(letters) >= 0.4

    @staticmethod
    def _ends_with_letter(text: str) -> bool:
        t = text.rstrip()
        return bool(t) and (_PERSIAN_RE.match(t[-1]) or t[-1].isalnum())

    @staticmethod
    def _starts_with_letter(text: str) -> bool:
        t = text.lstrip()
        return bool(t) and (_PERSIAN_RE.match(t[0]) or t[0].isalnum())

def repair_persian_years(text: str) -> str:
    """Repair high-confidence Gregorian years (1900–2099) in Persian/Arabic digits."""
    repaired, _ = repair_persian_years_with_changes(text)
    return repaired


def repair_persian_years_with_changes(text: str) -> tuple[str, list[RepairChange]]:
    changes: list[RepairChange] = []

    text = _repair_fragmented_year_forms(text, changes)
    text = _repair_reversed_four_digit_years(text, changes)
    return text, changes


def _repair_fragmented_year_forms(text: str, changes: list[RepairChange]) -> str:
    """Join fragmented year digits only when the result is a plausible Gregorian year."""

    def record(before: str, after: str) -> None:
        changes.append(RepairChange(kind="YEAR_FIX", before=before, after=after))

    def line_merge(match: re.Match[str]) -> str:
        first = match.group(1)
        second = match.group(2)
        persian = _resolve_gregorian_year_token(first + second)
        if persian is None:
            return match.group(0)
        record(f"{first}\n{second}", persian)
        return persian

    pattern = re.compile(
        rf"(?m)^([{_DIGITS_CLASS}]{{1,2}})\s*\n\s*([{_DIGITS_CLASS}]{{2,3}})\s*$",
    )
    text = pattern.sub(line_merge, text)

    def year_after_context(match: re.Match[str]) -> str:
        prefix = match.group(1)
        digits = match.group(2)
        if len(_digits_to_western(digits)) != 4:
            return match.group(0)
        persian = _resolve_gregorian_year_token(digits)
        if persian is None:
            return match.group(0)
        record(f"{prefix}\n{digits}", f"{prefix} {persian}")
        return f"{prefix} {persian}"

    context_year = re.compile(
        rf"(سال|در سال)\s*\n\s*([{_DIGITS_CLASS}]{{4}})\s*(?=\n|$)",
    )
    text = context_year.sub(year_after_context, text)

    inline = re.compile(rf"([{_DIGITS_CLASS}])\s+([{_DIGITS_CLASS}]{{2,3}})(?![{_DIGITS_CLASS}])")

    def inline_merge(match: re.Match[str]) -> str:
        combined = match.group(1) + match.group(2)
        persian = _resolve_gregorian_year_token(combined)
        if persian is None:
            return match.group(0)
        record(match.group(0), persian)
        return persian

    return inline.sub(inline_merge, text)


def _repair_reversed_four_digit_years(text: str, changes: list[RepairChange]) -> str:
    def replacer(match: re.Match[str]) -> str:
        token = match.group(1)
        fixed = _fix_reversed_year_token(token)
        if fixed is None:
            return token
        changes.append(RepairChange(kind="YEAR_FIX", before=token, after=fixed))
        return fixed

    return _YEAR_TOKEN.sub(replacer, text)


def _fix_reversed_year_token(token: str) -> str | None:
    """Fix RTL-reversed 4-digit Gregorian years; leave valid years unchanged."""
    if len(token) != 4:
        return None

    western = _digits_to_western(token)
    if not western.isdigit():
        return None

    canonical = _digits_to_persian(western)
    forward_ok = _is_gregorian_year(western)
    reversed_western = western[::-1]
    reverse_ok = _is_gregorian_year(reversed_western)

    if forward_ok:
        return None if token == canonical else canonical

    if reverse_ok and not forward_ok:
        return _digits_to_persian(reversed_western)

    return None


def _resolve_gregorian_year_token(digits: str) -> str | None:
    """Normalize a 4-digit token to Persian digits if it is (or reverses to) 1900–2099."""
    western = _digits_to_western(digits)
    if len(western) != 4 or not western.isdigit():
        return None

    if _is_gregorian_year(western):
        return _digits_to_persian(western)

    reversed_western = western[::-1]
    if _is_gregorian_year(reversed_western):
        return _digits_to_persian(reversed_western)

    return None


def _is_gregorian_year(western_four_digit: str) -> bool:
    if len(western_four_digit) != 4 or not western_four_digit.isdigit():
        return False
    year = int(western_four_digit)
    return _GREGORIAN_YEAR_MIN <= year <= _GREGORIAN_YEAR_MAX


def _digits_to_western(value: str) -> str:
    persian = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
    arabic = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    return value.translate(persian).translate(arabic)


def _digits_to_persian(value: str) -> str:
    western = _digits_to_western(value)
    return western.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
