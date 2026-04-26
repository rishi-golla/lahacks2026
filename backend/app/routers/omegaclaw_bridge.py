"""HTTP surface consumed by OmegaClaw-Core `channels/lahacks_http.py`."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from fastapi import APIRouter, Body, Header, HTTPException, Response

from ..omegaclaw_bridge import (
    auth_header_ok,
    bridge_enabled,
    complete_from_result,
    wait_next_job,
)

log = logging.getLogger(__name__)

router = APIRouter()


def _smoke_endpoint_enabled() -> bool:
    v = os.environ.get("OMEGACLAW_BRIDGE_SMOKE", "").strip().lower()
    return v in ("1", "true", "yes")


@router.get("/next")
async def omegaclaw_next(authorization: str | None = Header(None)) -> Response:
    if not bridge_enabled():
        raise HTTPException(status_code=404, detail="bridge disabled")
    if not auth_header_ok(authorization):
        raise HTTPException(status_code=401, detail="unauthorized")
    job = await wait_next_job(55.0)
    if job is None:
        return Response("", media_type="text/plain; charset=utf-8")
    line = "LAHACKS_TASK_JSON:" + json.dumps(job, separators=(",", ":"), ensure_ascii=False)
    return Response(line, media_type="text/plain; charset=utf-8")


@router.post("/result")
async def omegaclaw_result(
    authorization: str | None = Header(None),
    payload: dict = Body(default_factory=dict),
) -> dict[str, bool]:
    if not bridge_enabled():
        raise HTTPException(status_code=404, detail="bridge disabled")
    if not auth_header_ok(authorization):
        raise HTTPException(status_code=401, detail="unauthorized")
    body = payload
    request_id = str(body.get("request_id") or "")
    text = str(body.get("text") or "")
    ok = complete_from_result(request_id, text)
    return {"ok": ok}


@router.post("/smoke-submit")
async def omegaclaw_smoke_submit(authorization: str | None = Header(None)) -> dict:
    """Phase 4 helper: enqueue one `BackendChannel` job and wait for OmegaClaw POST /result.

    Enable with ``OMEGACLAW_BRIDGE_SMOKE=1`` (and ``OMEGACLAW_BRIDGE_ENABLED=1``).
    Requires the same ``Authorization`` bearer as other bridge routes when a bridge secret is set.
    """
    if not _smoke_endpoint_enabled():
        raise HTTPException(status_code=404, detail="smoke disabled")
    if not bridge_enabled():
        raise HTTPException(status_code=404, detail="bridge disabled")
    if not auth_header_ok(authorization):
        raise HTTPException(status_code=401, detail="unauthorized")

    repo_root = Path(__file__).resolve().parents[3]
    root_s = str(repo_root)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)

    from omegaclaw.channels.backend_channel import BackendChannel, GlassesTask

    task = GlassesTask(
        session_id="smoke-session",
        turn_id="smoke-turn",
        intent="Use lahacks-echo on the text hello, then reply with a final (send ...) JSON per the system prompt.",
        tool_call_id="smoke-tool-call",
        args={"skill_name": "lahacks_echo", "text": "hello"},
    )
    try:
        out = await BackendChannel().submit(task)
    except Exception:
        log.exception("omegaclaw smoke-submit failed")
        raise HTTPException(status_code=500, detail="submit failed") from None
    log.info("omegaclaw smoke-submit completed source=%s", out.get("source"))
    return {"ok": True, "result": out}
