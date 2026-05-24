"""Simple round-robin API key pool for Gemini TTS."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from backend.services.token_config import load_enabled_tokens

logger = logging.getLogger(__name__)


class GenerationCancelled(Exception):
    """Raised when the user cancels during a quota wait."""


class TokenPool:
    def __init__(self, tokens_file: Path, wait_seconds: int = 45) -> None:
        self._tokens = load_enabled_tokens(tokens_file)
        self._wait_seconds = wait_seconds
        self._index = 0
        self._cycles = 0
        self.quota_failovers = 0

    @property
    def total(self) -> int:
        return len(self._tokens)

    @property
    def wait_seconds(self) -> int:
        return self._wait_seconds

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
            self.quota_failovers += 1
            logger.warning(
                "Switching to token %s (%s/%s)",
                self.current_name(),
                self.current_index,
                self.total,
            )
            return True
        return False

    def wait_and_reset(
        self,
        *,
        cancel_checker: Callable[[], bool] | None = None,
        on_tick: Callable[[int], None] | None = None,
    ) -> None:
        self._cycles += 1
        logger.warning(
            "All tokens exhausted — waiting %ss before retry (cycle %s)",
            self._wait_seconds,
            self._cycles,
        )
        for remaining in range(self._wait_seconds, 0, -1):
            if cancel_checker and cancel_checker():
                raise GenerationCancelled("Generation cancelled during quota wait.")
            if on_tick:
                on_tick(remaining)
            time.sleep(1)
        self._index = 0
