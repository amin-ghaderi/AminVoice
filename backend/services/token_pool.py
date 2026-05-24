"""Simple round-robin API key pool for Gemini TTS."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class TokenPool:
    def __init__(self, tokens_file: Path, wait_seconds: int = 45) -> None:
        self._tokens = self._load_tokens(tokens_file)
        self._wait_seconds = wait_seconds
        self._index = 0
        self._cycles = 0

    @property
    def total(self) -> int:
        return len(self._tokens)

    @property
    def current_index(self) -> int:
        return self._index + 1

    def current_name(self) -> str:
        return self._tokens[self._index]["name"]

    def current_key(self) -> str:
        if not self._tokens:
            raise RuntimeError("No Gemini API tokens configured.")
        return self._tokens[self._index]["api_key"]

    def advance(self) -> bool:
        """Move to next token. Returns False if all tokens were tried this cycle."""
        if not self._tokens:
            return False
        if self._index + 1 < len(self._tokens):
            self._index += 1
            logger.warning("Switching to token %s (%s/%s)", self.current_name(), self.current_index, self.total)
            return True
        return False

    def wait_and_reset(self) -> None:
        self._cycles += 1
        logger.warning(
            "All tokens exhausted — waiting %ss before retry (cycle %s)",
            self._wait_seconds,
            self._cycles,
        )
        time.sleep(self._wait_seconds)
        self._index = 0

    @staticmethod
    def _load_tokens(tokens_file: Path) -> list[dict[str, str]]:
        tokens: list[dict[str, str]] = []

        if tokens_file.exists():
            raw = json.loads(tokens_file.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for item in raw:
                    key = item.get("api_key") or item.get("key")
                    if key:
                        tokens.append(
                            {
                                "name": item.get("name") or item.get("id") or "token",
                                "api_key": key,
                            }
                        )

        if not tokens:
            env_key = os.environ.get("GEMINI_API_KEY")
            if env_key:
                tokens.append({"name": "env", "api_key": env_key})

        return tokens
