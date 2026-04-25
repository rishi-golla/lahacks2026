"""Stateful helper for look-request tool calls that need client photo capture."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from .protocol import PhotoFrame, PhotoTrigger


DEFAULT_LOOK_TIMEOUT_MS = 10_000


class LookLoopState(StrEnum):
    PENDING = "pending"
    FULFILLED = "fulfilled"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LookLoopError(Exception):
    """Base exception for look-loop correlation failures."""


class DuplicateLookRequestError(LookLoopError):
    """Raised when a pending request already exists for a tool call."""


class UnknownLookRequestError(LookLoopError):
    """Raised when a tool call cannot be correlated to a known request."""


@dataclass(frozen=True, slots=True)
class LookRequest:
    tool_call_id: str
    reason: str
    requested_at_ms: int
    timeout_ms: int
    deadline_ms: int
    state: LookLoopState = LookLoopState.PENDING
    photo_jpeg_b64: str | None = None
    photo_ts_ms: int | None = None
    failure_reason: str | None = None

    def to_client_payload(self) -> dict[str, str]:
        return {
            "type": "look_request",
            "tool_call_id": self.tool_call_id,
            "reason": self.reason,
        }


class LookLoop:
    """Tracks pending look tool calls until a photo, timeout, or failure resolves them."""

    def __init__(self, *, default_timeout_ms: int = DEFAULT_LOOK_TIMEOUT_MS) -> None:
        if default_timeout_ms <= 0:
            raise ValueError("default_timeout_ms must be greater than zero")
        self._default_timeout_ms = default_timeout_ms
        self._pending: dict[str, LookRequest] = {}

    def create_request(
        self,
        *,
        tool_call_id: str,
        reason: str,
        requested_at_ms: int,
        timeout_ms: int | None = None,
    ) -> LookRequest:
        if not tool_call_id:
            raise ValueError("tool_call_id must be a non-empty string")
        if not reason:
            raise ValueError("reason must be a non-empty string")
        if tool_call_id in self._pending:
            raise DuplicateLookRequestError(f"look request already pending for {tool_call_id}")

        effective_timeout_ms = timeout_ms if timeout_ms is not None else self._default_timeout_ms
        if effective_timeout_ms <= 0:
            raise ValueError("timeout_ms must be greater than zero")

        request = LookRequest(
            tool_call_id=tool_call_id,
            reason=reason,
            requested_at_ms=requested_at_ms,
            timeout_ms=effective_timeout_ms,
            deadline_ms=requested_at_ms + effective_timeout_ms,
        )
        self._pending[tool_call_id] = request
        return request

    def complete_request(self, photo: PhotoFrame) -> LookRequest:
        if photo.trigger is not PhotoTrigger.TOOL_LOOK:
            raise ValueError("look loop only accepts tool_look photo frames")
        if not photo.tool_call_id:
            raise ValueError("tool_look photos must include tool_call_id")

        request = self._pop_pending(photo.tool_call_id)
        return replace(
            request,
            state=LookLoopState.FULFILLED,
            photo_jpeg_b64=photo.jpeg_b64,
            photo_ts_ms=photo.ts_ms,
            failure_reason=None,
        )

    def fail_request(self, tool_call_id: str, reason: str) -> LookRequest:
        request = self._pop_pending(tool_call_id)
        return replace(request, state=LookLoopState.FAILED, failure_reason=reason)

    def cancel_request(self, tool_call_id: str, reason: str = "look request cancelled") -> LookRequest:
        request = self._pop_pending(tool_call_id)
        return replace(request, state=LookLoopState.CANCELLED, failure_reason=reason)

    def expire_requests(self, *, now_ms: int) -> list[LookRequest]:
        expired_ids = [
            tool_call_id
            for tool_call_id, request in self._pending.items()
            if now_ms >= request.deadline_ms
        ]
        expired: list[LookRequest] = []
        for tool_call_id in expired_ids:
            request = self._pending.pop(tool_call_id)
            expired.append(
                replace(
                    request,
                    state=LookLoopState.TIMED_OUT,
                    failure_reason="look request timed out",
                )
            )
        return expired

    def get_pending_request(self, tool_call_id: str) -> LookRequest | None:
        return self._pending.get(tool_call_id)

    def has_pending_request(self, tool_call_id: str) -> bool:
        return tool_call_id in self._pending

    def pending_tool_call_ids(self) -> tuple[str, ...]:
        return tuple(self._pending)

    def _pop_pending(self, tool_call_id: str) -> LookRequest:
        try:
            return self._pending.pop(tool_call_id)
        except KeyError as exc:
            raise UnknownLookRequestError(f"unknown look request: {tool_call_id}") from exc
