"""Tests for token config file helpers."""

from __future__ import annotations

from pathlib import Path

from backend.services.token_config import (
    TokenEntry,
    has_configured_tokens,
    is_masked_placeholder,
    load_enabled_tokens,
    load_tokens,
    mask_api_key,
    merge_saved_keys,
    save_tokens,
)


def test_mask_api_key():
    assert mask_api_key("AIzaSyABCDEF1234567890").startswith("AIza")
    assert "•" in mask_api_key("AIzaSyABCDEF1234567890")


def test_load_and_save_enabled_flag(tmp_path: Path):
    path = tmp_path / "projects.json"
    save_tokens(
        path,
        [
            TokenEntry(name="a", api_key="key-a", enabled=True),
            TokenEntry(name="b", api_key="key-b", enabled=False),
        ],
    )
    loaded = load_tokens(path)
    assert len(loaded) == 2
    assert loaded[1].enabled is False
    enabled = load_enabled_tokens(path)
    assert len(enabled) == 1
    assert enabled[0]["name"] == "a"


def test_merge_saved_keys_preserves_secret(tmp_path: Path):
    existing = [TokenEntry(name="main", api_key="secret-key-12345", enabled=True)]
    incoming = [
        TokenEntry(name="main", api_key=mask_api_key("secret-key-12345"), enabled=True)
    ]
    merged = merge_saved_keys(incoming, existing)
    assert merged[0].api_key == "secret-key-12345"


def test_is_masked_placeholder():
    assert is_masked_placeholder("AIza••••••••1234")
    assert not is_masked_placeholder("AIzaSyRealKey")


def test_has_configured_tokens_false_when_empty(tmp_path: Path, monkeypatch):
    path = tmp_path / "projects.json"
    path.write_text("[]", encoding="utf-8")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert has_configured_tokens(path) is False
