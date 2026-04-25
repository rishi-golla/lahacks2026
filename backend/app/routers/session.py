"""WebSocket /session endpoint."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

from ..session import SessionCoordinator

router = APIRouter(tags=["session"])


@router.websocket("/session")
async def session_endpoint(ws: WebSocket) -> None:
    coordinator = SessionCoordinator()
    await coordinator.run(ws)
