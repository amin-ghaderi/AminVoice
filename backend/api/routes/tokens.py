"""Gemini API token management (file-backed, no database)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_app_settings
from backend.config.settings import Settings
from backend.schemas.tokens import (
    TokenListResponse,
    TokenMonitorItem,
    TokenPublic,
    TokenRuntimeStatusResponse,
    TokenSaveRequest,
    TokenTestRequest,
    TokenTestResponse,
    UsageHistoryItem,
    SwitchHistoryItem,
)
from backend.services.token_config import (
    TokenEntry,
    has_configured_tokens,
    load_tokens,
    merge_saved_keys,
    save_tokens,
)
from backend.services.token_pool_monitor import get_token_pool_monitor
from backend.services.token_tester import test_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tokens", tags=["tokens"])


def _public_list(settings: Settings) -> list[TokenPublic]:
    entries = load_tokens(settings.tokens_file)
    return [
        TokenPublic(**entry.to_public_dict(priority=index))
        for index, entry in enumerate(entries, start=1)
    ]


def _idle_runtime_payload(settings: Settings) -> TokenRuntimeStatusResponse:
    entries = [e for e in load_tokens(settings.tokens_file) if e.enabled]
    tokens = [
        TokenMonitorItem(name=entry.name, priority=index, status="idle")
        for index, entry in enumerate(entries, start=1)
    ]
    return TokenRuntimeStatusResponse(
        active=False,
        generation_active=False,
        total_tokens=len(tokens),
        tokens=tokens,
    )


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
) -> TokenRuntimeStatusResponse:
    snap = get_token_pool_monitor().snapshot()
    if not snap.get("generation_active"):
        idle = _idle_runtime_payload(settings)
        if snap.get("switch_history") or snap.get("usage_history"):
            idle.switch_history = [SwitchHistoryItem(**item) for item in snap["switch_history"]]
            idle.usage_history = [UsageHistoryItem(**item) for item in snap["usage_history"]]
        return idle

    return TokenRuntimeStatusResponse(
        active=True,
        generation_active=True,
        intake_id=snap.get("intake_id"),
        total_tokens=snap.get("total_tokens", 0),
        active_token_index=snap.get("active_token_index", 0),
        active_token_name=snap.get("active_token_name"),
        now_using=snap.get("now_using"),
        current_token_name=snap.get("active_token_name"),
        failed_tokens=snap.get("failed_tokens", []),
        pool_waiting=snap.get("pool_waiting", False),
        current_chunk=snap.get("current_chunk", 0),
        total_chunks=snap.get("total_chunks", 0),
        quota_failovers=snap.get("quota_failovers", 0),
        tokens=[TokenMonitorItem(**item) for item in snap.get("tokens", [])],
        usage_history=[UsageHistoryItem(**item) for item in snap.get("usage_history", [])],
        switch_history=[SwitchHistoryItem(**item) for item in snap.get("switch_history", [])],
    )
