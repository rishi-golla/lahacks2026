"""OmegaClaw custom backend channel adapter.

This module mirrors the OmegaClaw-Core channel contract:
  - start_my_backend(...)
  - getLastMessage()
  - send_message(str)

It also exposes async helpers for the FastAPI side to enqueue work and await
responses while still flowing through one channel-driven agent loop.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class BackendRuntimeParams:
    backend_url: str = ""
    auth_secret: str | None = None
    poll_interval_ms: int = 50


_params = BackendRuntimeParams()
_started = False
_inbound: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
_pending: dict[str, asyncio.Future[dict[str, Any]]] = {}


def start_my_backend(
    backend_url: str = "",
    auth_secret: str | None = None,
    poll_interval_ms: int = 50,
) -> None:
    """Initialize channel runtime parameters for OmegaClaw loop startup."""
    global _params, _started
    _params = BackendRuntimeParams(
        backend_url=backend_url,
        auth_secret=auth_secret,
        poll_interval_ms=poll_interval_ms,
    )
    _started = True


def getLastMessage() -> dict[str, Any] | None:  # noqa: N802 (OmegaClaw contract)
    """Return the next message for the agent loop, if present."""
    if not _started:
        return None
    try:
        return _inbound.get_nowait()
    except asyncio.QueueEmpty:
        return None


def send_message(text: str) -> None:
    """Send an agent-loop response back to the waiting backend caller."""
    payload: dict[str, Any]
    try:
        decoded = json.loads(text)
        payload = decoded if isinstance(decoded, dict) else {"raw": decoded}
    except json.JSONDecodeError:
        payload = {"result": {"summary": text, "confidence": "low", "source": "loop"}}

    request_id = str(payload.get("request_id", ""))
    if not request_id:
        return

    fut = _pending.pop(request_id, None)
    if fut is None or fut.done():
        return
    fut.set_result(payload)


def enqueue_message(message: dict[str, Any]) -> tuple[str, asyncio.Future[dict[str, Any]]]:
    """Queue a backend message for consumption by the OmegaClaw agent loop."""
    if not _started:
        start_my_backend()

    request_id = str(message.get("request_id") or uuid4())
    message = dict(message)
    message["request_id"] = request_id

    loop = asyncio.get_running_loop()
    fut: asyncio.Future[dict[str, Any]] = loop.create_future()
    _pending[request_id] = fut
    _inbound.put_nowait(message)
    return request_id, fut


def runtime_params() -> BackendRuntimeParams:
    """Expose current runtime params for diagnostics and docs."""
    return _params
