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


class TokenRuntimeStatusResponse(BaseModel):
    active: bool
    current_token_name: str | None = None
    intake_id: str | None = None
    current_chunk: int = 0
    total_chunks: int = 0
    quota_failovers: int = 0
