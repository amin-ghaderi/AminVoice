"""Schemas for Gemini token management API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TokenPublic(BaseModel):
    name: str
    api_key_masked: str
    enabled: bool = True
    priority: int


class TokenInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    api_key: str = Field(min_length=1)
    enabled: bool = True


class TokenListResponse(BaseModel):
    tokens: list[TokenPublic]
    configured: bool


class TokenSaveRequest(BaseModel):
    tokens: list[TokenInput]


class TokenTestRequest(BaseModel):
    api_key: str | None = None
    name: str | None = None


class TokenTestResponse(BaseModel):
    result: str
    message: str


class TokenMonitorItem(BaseModel):
    name: str
    priority: int
    status: str


class UsageHistoryItem(BaseModel):
    token: str
    chunk_id: int
    status: str
    at: float


class SwitchHistoryItem(BaseModel):
    from_token: str
    to_token: str
    reason: str
    chunk_id: int
    at: float


class TokenRuntimeStatusResponse(BaseModel):
    """Token pool observability — safe to poll during generation."""

    active: bool = False
    generation_active: bool = False
    intake_id: str | None = None
    total_tokens: int = 0
    active_token_index: int = 0
    active_token_name: str | None = None
    now_using: str | None = None
    failed_tokens: list[str] = Field(default_factory=list)
    pool_waiting: bool = False
    current_chunk: int = 0
    total_chunks: int = 0
    quota_failovers: int = 0
    current_token_name: str | None = None
    tokens: list[TokenMonitorItem] = Field(default_factory=list)
    usage_history: list[UsageHistoryItem] = Field(default_factory=list)
    switch_history: list[SwitchHistoryItem] = Field(default_factory=list)
