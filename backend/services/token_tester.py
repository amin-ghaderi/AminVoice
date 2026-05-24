"""Lightweight Gemini API key validation."""

from __future__ import annotations

import logging

from google import genai

logger = logging.getLogger(__name__)


def test_api_key(api_key: str) -> tuple[str, str]:
    """
    Returns (result, message) where result is 'ok' | 'invalid' | 'quota'.
    """
    key = api_key.strip()
    if not key:
        return "invalid", "API key is empty."

    client = genai.Client(api_key=key)
    try:
        # Minimal call — list models (does not consume TTS quota).
        for _ in client.models.list():
            break
        return "ok", "Token is valid and reachable."
    except Exception as exc:
        message = str(exc)
        upper = message.upper()
        logger.info("Token test failed: %s", message)
        if "429" in message or "RESOURCE_EXHAUSTED" in upper or "QUOTA" in upper:
            return "quota", "Quota exhausted or rate limited — key works but cannot call API now."
        if any(
            token in upper
            for token in ("API_KEY_INVALID", "INVALID API KEY", "UNAUTHENTICATED", "401", "403")
        ):
            return "invalid", "Invalid API key."
        return "invalid", message[:200] if message else "Could not validate token."
