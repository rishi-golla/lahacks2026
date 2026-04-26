"""In-process queue and waiters for OmegaClaw-Core HTTP bridge (LA Hacks).

OmegaClaw's `lahacks_http` channel long-polls GET /internal/omegaclaw/next on this
process. Gemini's `agent` tool calls enqueue_and_wait(), which blocks until
POST /internal/omegaclaw/result completes the same request_id.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import uuid
from typing import Any

log = logging.getLogger(__name__)

_queue: asyncio.Queue[dict[str, Any]] | None = None
_waiters: dict[str, asyncio.Future[dict[str, Any]]] = {}
_state_lock = threading.Lock()


def bridge_enabled() -> bool:
    v = os.environ.get("OMEGACLAW_BRIDGE_ENABLED", "").strip().lower()
    return v in ("1", "true", "yes")


def bridge_secret_expected() -> str:
    return os.environ.get("OMEGACLAW_BRIDGE_SECRET", "").strip()


def auth_header_ok(authorization: str | None) -> bool:
    expected = bridge_secret_expected()
    if not expected:
        return True
    if not authorization:
        return False
    return authorization.strip() == f"Bearer {expected}"


def _queue_get() -> asyncio.Queue[dict[str, Any]]:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


async def wait_next_job(timeout_s: float) -> dict[str, Any] | None:
    q = _queue_get()
    try:
        return await asyncio.wait_for(q.get(), timeout=timeout_s)
    except asyncio.TimeoutError:
        return None


def normalize_send_payload(request_id: str, text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "result" in parsed:
            out = dict(parsed)
            out.setdefault("request_id", request_id or out.get("request_id", ""))
            return out
        if isinstance(parsed, dict):
            return {"request_id": request_id, "result": parsed}
    except json.JSONDecodeError:
        pass
    return {
        "request_id": request_id,
        "result": {
            "summary": text,
            "confidence": "medium",
            "source": "omegaclaw:send_text",
        },
    }


def complete_from_result(request_id: str | None, text: str) -> bool:
    rid = (request_id or "").strip()
    if not rid:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                rid = str(parsed.get("request_id", "") or "")
        except json.JSONDecodeError:
            rid = ""
    if not rid:
        log.warning("omegaclaw bridge result missing request_id")
        return False
    with _state_lock:
        fut = _waiters.pop(rid, None)
    if fut is None or fut.done():
        log.warning("omegaclaw bridge: stale or unknown request_id=%s", rid)
        return False
    payload = normalize_send_payload(rid, text)
    fut.set_result(payload)
    return True


async def enqueue_and_wait(job: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    q = _queue_get()
    rid = str(job.get("request_id") or uuid.uuid4())
    payload = dict(job)
    payload["request_id"] = rid
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[dict[str, Any]] = loop.create_future()
    with _state_lock:
        if _waiters:
            return {
                "request_id": rid,
                "result": {
                    "summary": "OmegaClaw is already handling another request. Please try again in a moment.",
                    "confidence": "low",
                    "source": "omegaclaw:busy",
                    "error": "bridge_busy",
                },
            }
        _waiters[rid] = fut
    await q.put(payload)
    try:
        return await asyncio.wait_for(fut, timeout=timeout_s)
    except asyncio.TimeoutError:
        with _state_lock:
            _waiters.pop(rid, None)
        if not fut.done():
            fut.cancel()
        raise
    finally:
        with _state_lock:
            _waiters.pop(rid, None)
