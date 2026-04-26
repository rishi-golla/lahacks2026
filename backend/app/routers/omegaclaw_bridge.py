"""HTTP surface consumed by OmegaClaw-Core `channels/lahacks_http.py`."""

from __future__ import annotations

import json

from fastapi import APIRouter, Body, Header, HTTPException, Response

from ..omegaclaw_bridge import (
    auth_header_ok,
    bridge_enabled,
    complete_from_result,
    wait_next_job,
)

router = APIRouter()


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
