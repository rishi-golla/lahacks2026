"""WebSocket /session endpoint.

Phase 1 (current): dumb echo server. Accepts JSON messages, logs them, and
echoes them back wrapped in {"type": "echo", "received": <msg>}. This exists so
the iOS app has something real to connect to before the Gemini Live bridge is
wired up.

Phase 4 (next): replaced by the real SessionCoordinator in
``app.session.coordinator`` which proxies to Gemini Live and dispatches tool
calls.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["session"])
log = logging.getLogger(__name__)


@router.websocket("/session")
async def session_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    client = f"{ws.client.host}:{ws.client.port}" if ws.client else "unknown"
    log.info("session connected client=%s", client)

    try:
        while True:
            raw = await ws.receive_text()
            msg = _parse(raw)
            if msg is None:
                await _send(ws, {"type": "error", "message": "invalid JSON"})
                continue

            log.info("session received client=%s type=%s", client, msg.get("type", "?"))
            await _send(ws, {"type": "echo", "received": msg})
    except WebSocketDisconnect:
        log.info("session disconnected client=%s", client)
    except Exception as exc:  # noqa: BLE001 — log + close on anything unexpected
        log.exception("session error client=%s: %s", client, exc)
        try:
            await ws.close(code=1011)
        except RuntimeError:
            pass


def _parse(raw: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def _send(ws: WebSocket, payload: dict[str, Any]) -> None:
    await ws.send_text(json.dumps(payload))
