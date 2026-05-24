"""Read/write Gemini API tokens from tokens/projects.json (no database)."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MASK_CHAR = "•"


@dataclass
class TokenEntry:
    name: str
    api_key: str
    enabled: bool = True

    def to_file_dict(self) -> dict:
        return {
            "name": self.name,
            "api_key": self.api_key,
            "enabled": self.enabled,
        }

    def to_public_dict(self, *, priority: int) -> dict:
        return {
            "name": self.name,
            "api_key_masked": mask_api_key(self.api_key),
            "enabled": self.enabled,
            "priority": priority,
        }


def mask_api_key(api_key: str) -> str:
    key = (api_key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return key[:3] + MASK_CHAR * 6
    return key[:4] + MASK_CHAR * 8 + key[-4:]


def is_masked_placeholder(value: str) -> bool:
    return MASK_CHAR in value or value.endswith("****")


def load_tokens(tokens_file: Path) -> list[TokenEntry]:
    if not tokens_file.exists():
        return []

    raw = json.loads(tokens_file.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []

    entries: list[TokenEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = (item.get("api_key") or item.get("key") or "").strip()
        if not key:
            continue
        enabled = item.get("enabled", True)
        if isinstance(enabled, str):
            enabled = enabled.lower() in ("1", "true", "yes")
        entries.append(
            TokenEntry(
                name=(item.get("name") or item.get("id") or "token").strip(),
                api_key=key,
                enabled=bool(enabled),
            )
        )
    return entries


def load_enabled_tokens(tokens_file: Path) -> list[dict[str, str]]:
    """Tokens for TokenPool — enabled entries only, in priority order."""
    enabled = [entry for entry in load_tokens(tokens_file) if entry.enabled]
    if enabled:
        return [{"name": t.name, "api_key": t.api_key} for t in enabled]

    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        logger.info("Using GEMINI_API_KEY from environment (no enabled tokens in file).")
        return [{"name": "env", "api_key": env_key}]
    return []


def save_tokens(tokens_file: Path, entries: list[TokenEntry]) -> None:
    tokens_file.parent.mkdir(parents=True, exist_ok=True)
    payload = [entry.to_file_dict() for entry in entries]
    tokens_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def merge_saved_keys(
    incoming: list[TokenEntry],
    existing: list[TokenEntry],
) -> list[TokenEntry]:
    """Preserve real API keys when the UI sends masked placeholders."""
    by_name = {item.name: item.api_key for item in existing}
    merged: list[TokenEntry] = []
    for item in incoming:
        key = item.api_key.strip()
        if is_masked_placeholder(key) and item.name in by_name:
            key = by_name[item.name]
        merged.append(TokenEntry(name=item.name, api_key=key, enabled=item.enabled))
    return merged


def has_configured_tokens(tokens_file: Path) -> bool:
    if any(entry.enabled for entry in load_tokens(tokens_file)):
        return True
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())
