"""Read-only runtime tracking for Gemini token pool (does not affect failover)."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MAX_USAGE_HISTORY = 50
MAX_SWITCH_HISTORY = 10


@dataclass
class UsageRecord:
    token: str
    chunk_id: int
    status: str
    at: float = field(default_factory=time.time)


@dataclass
class SwitchEvent:
    from_token: str
    to_token: str
    reason: str
    chunk_id: int
    at: float = field(default_factory=time.time)


@dataclass
class TokenPoolState:
    generation_active: bool = False
    intake_id: str | None = None
    total_tokens: int = 0
    active_token_index: int = 0
    active_token_name: str = ""
    failed_tokens: list[str] = field(default_factory=list)
    pool_waiting: bool = False
    current_chunk: int = 0
    total_chunks: int = 0
    token_names: list[str] = field(default_factory=list)
    usage_history: list[UsageRecord] = field(default_factory=list)
    switch_history: list[SwitchEvent] = field(default_factory=list)

    def to_api_dict(self) -> dict:
        failed_set = set(self.failed_tokens)
        active_name = self.active_token_name
        tokens = []
        for index, name in enumerate(self.token_names, start=1):
            if self.pool_waiting:
                status = "waiting"
            elif name == active_name and self.generation_active:
                status = "active"
            elif name in failed_set:
                status = "failed"
            else:
                status = "idle"
            tokens.append(
                {
                    "name": name,
                    "priority": index,
                    "status": status,
                }
            )

        return {
            "generation_active": self.generation_active,
            "intake_id": self.intake_id,
            "total_tokens": self.total_tokens,
            "active_token_index": self.active_token_index,
            "active_token_name": self.active_token_name,
            "now_using": self.active_token_name or None,
            "failed_tokens": list(self.failed_tokens),
            "pool_waiting": self.pool_waiting,
            "current_chunk": self.current_chunk,
            "total_chunks": self.total_chunks,
            "quota_failovers": len(self.switch_history),
            "tokens": tokens,
            "usage_history": [
                {
                    "token": item.token,
                    "chunk_id": item.chunk_id,
                    "status": item.status,
                    "at": item.at,
                }
                for item in self.usage_history[-20:]
            ],
            "switch_history": [
                {
                    "from_token": item.from_token,
                    "to_token": item.to_token,
                    "reason": item.reason,
                    "chunk_id": item.chunk_id,
                    "at": item.at,
                }
                for item in self.switch_history[-MAX_SWITCH_HISTORY:]
            ],
        }


class TokenPoolMonitor:
    """Thread-safe observability store for token pool activity."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = TokenPoolState()

    def begin_run(self, intake_id: str, token_names: list[str], total_chunks: int) -> None:
        with self._lock:
            self._state = TokenPoolState(
                generation_active=True,
                intake_id=intake_id,
                total_tokens=len(token_names),
                token_names=list(token_names),
                active_token_index=1 if token_names else 0,
                active_token_name=token_names[0] if token_names else "",
                total_chunks=total_chunks,
                current_chunk=0,
            )
        logger.info("Token pool monitor: run started (%s tokens)", len(token_names))

    def end_run(self) -> None:
        with self._lock:
            self._state.generation_active = False
            self._state.pool_waiting = False

    def set_current_chunk(self, chunk_id: int) -> None:
        with self._lock:
            self._state.current_chunk = chunk_id

    def sync_active(self, token_name: str, token_index: int) -> None:
        with self._lock:
            self._state.active_token_name = token_name
            self._state.active_token_index = token_index
            self._state.pool_waiting = False

    def record_token_used(self, token_name: str, chunk_id: int, status: str = "calling") -> None:
        with self._lock:
            self._state.active_token_name = token_name
            self._append_usage(token_name, chunk_id, status)
        logger.info("Token monitor: chunk %s using %s (%s)", chunk_id, token_name, status)

    def record_quota_failure(self, token_name: str, chunk_id: int) -> None:
        with self._lock:
            if token_name not in self._state.failed_tokens:
                self._state.failed_tokens.append(token_name)
            self._append_usage(token_name, chunk_id, "quota_failed")
        logger.info("Token monitor: quota hit on %s (chunk %s)", token_name, chunk_id)

    def record_switch(self, from_token: str, to_token: str, reason: str, chunk_id: int) -> None:
        with self._lock:
            self._state.active_token_name = to_token
            if self._state.token_names:
                try:
                    self._state.active_token_index = (
                        self._state.token_names.index(to_token) + 1
                    )
                except ValueError:
                    pass
            self._state.pool_waiting = False
            self._state.switch_history.append(
                SwitchEvent(
                    from_token=from_token,
                    to_token=to_token,
                    reason=reason,
                    chunk_id=chunk_id,
                )
            )
            if len(self._state.switch_history) > MAX_SWITCH_HISTORY:
                self._state.switch_history = self._state.switch_history[-MAX_SWITCH_HISTORY:]
            self._append_usage(to_token, chunk_id, "switched")
        logger.info(
            "Token monitor: switch %s → %s (%s) chunk %s",
            from_token,
            to_token,
            reason,
            chunk_id,
        )

    def record_pool_waiting(self, wait_seconds: int) -> None:
        with self._lock:
            self._state.pool_waiting = True
            self._append_usage(
                self._state.active_token_name or "pool",
                self._state.current_chunk,
                f"waiting_{wait_seconds}s",
            )
        logger.info("Token monitor: all tokens waiting (%ss)", wait_seconds)

    def record_chunk_success(self, token_name: str, chunk_id: int) -> None:
        with self._lock:
            self._append_usage(token_name, chunk_id, "success")
            if token_name in self._state.failed_tokens:
                self._state.failed_tokens = [
                    name for name in self._state.failed_tokens if name != token_name
                ]

    def snapshot(self) -> dict:
        with self._lock:
            return self._state.to_api_dict()

    def _append_usage(self, token_name: str, chunk_id: int, status: str) -> None:
        self._state.usage_history.append(
            UsageRecord(token=token_name, chunk_id=chunk_id, status=status)
        )
        if len(self._state.usage_history) > MAX_USAGE_HISTORY:
            self._state.usage_history = self._state.usage_history[-MAX_USAGE_HISTORY:]


_monitor = TokenPoolMonitor()


def get_token_pool_monitor() -> TokenPoolMonitor:
    return _monitor
