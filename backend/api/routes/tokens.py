"""Gemini API token management (file-backed, no database)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_audiobook_generator, get_app_settings
from backend.config.settings import Settings
from backend.schemas.tokens import (
    TokenListResponse,
    TokenPublic,
    TokenRuntimeStatusResponse,
    TokenSaveRequest,
    TokenTestRequest,
    TokenTestResponse,
)
from backend.services.audiobook_generator import AudiobookGenerator
from backend.services.token_config import (
    TokenEntry,
    has_configured_tokens,
    load_tokens,
    merge_saved_keys,
    mask_api_key,
    save_tokens,
)
from backend.services.token_tester import test_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tokens", tags=["tokens"])


def _public_list(settings: Settings) -> list[TokenPublic]:
    entries = load_tokens(settings.tokens_file)
    return [
        TokenPublic(**entry.to_public_dict(priority=index))
        for index, entry in enumerate(entries, start=1)
    ]


@router.get("", response_model=TokenListResponse)
def list_tokens(settings: Settings = Depends(get_app_settings)) -> TokenListResponse:
    return TokenListResponse(
        tokens=_public_list(settings),
        configured=has_configured_tokens(settings.tokens_file),
    )


@router.put("", response_model=TokenListResponse)
def save_token_list(
    body: TokenSaveRequest,
    settings: Settings = Depends(get_app_settings),
) -> TokenListResponse:
    if not body.tokens:
        save_tokens(settings.tokens_file, [])
        return TokenListResponse(tokens=[], configured=has_configured_tokens(settings.tokens_file))

    incoming: list[TokenEntry] = []
    for item in body.tokens:
        name = item.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Project name is required.")
        incoming.append(
            TokenEntry(name=name, api_key=item.api_key.strip(), enabled=item.enabled)
        )
    names = [item.name for item in incoming]
    if len(names) != len(set(names)):
        raise HTTPException(status_code=400, detail="Each project name must be unique.")

    existing = load_tokens(settings.tokens_file)
    merged = merge_saved_keys(incoming, existing)
    save_tokens(settings.tokens_file, merged)
    logger.info("Saved %s token(s) to projects.json", len(merged))
    return TokenListResponse(
        tokens=_public_list(settings),
        configured=has_configured_tokens(settings.tokens_file),
    )


@router.post("/test", response_model=TokenTestResponse)
def test_token(
    body: TokenTestRequest,
    settings: Settings = Depends(get_app_settings),
) -> TokenTestResponse:
    api_key = (body.api_key or "").strip()
    if not api_key and body.name:
        match = next((t for t in load_tokens(settings.tokens_file) if t.name == body.name), None)
        if match is None:
            raise HTTPException(status_code=404, detail="Token not found.")
        api_key = match.api_key

    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required.")

    result, message = test_api_key(api_key)
    icons = {"ok": "✅ Working", "invalid": "❌ Invalid key", "quota": "⚠️ Quota exhausted"}
    return TokenTestResponse(result=result, message=icons.get(result, message) + " — " + message)


@router.get("/runtime-status", response_model=TokenRuntimeStatusResponse)
def token_runtime_status(
    settings: Settings = Depends(get_app_settings),
    generator: AudiobookGenerator = Depends(get_audiobook_generator),
) -> TokenRuntimeStatusResponse:
    active = generator.status_store.find_active()
    if active is None:
        return TokenRuntimeStatusResponse(active=False)

    return TokenRuntimeStatusResponse(
        active=True,
        current_token_name=active.current_token_name or None,
        intake_id=active.intake_id,
        current_chunk=active.current_chunk,
        total_chunks=active.total_chunks,
        quota_failovers=active.quota_failovers,
    )
