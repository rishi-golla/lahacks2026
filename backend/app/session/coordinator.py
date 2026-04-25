"""Session coordination for the `/session` WebSocket.

This module owns the client-facing session loop while keeping integration seams
lightweight for the upcoming Gemini Live bridge, session state machine, and
tool-routing work.
"""

from __future__ import annotations

from dataclasses import asdict
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect

from .protocol import (
    ClientMessage,
    HelloMessage,
    ProtocolError,
    error_payload,
    parse_client_message,
)
from .state import SessionLifecycleState, StateTransitionError

log = logging.getLogger(__name__)


class LiveAdapter(Protocol):
    """Bridge between the websocket session and the live model runtime."""

    model_name: str

    async def open(self, session: "SessionContext", hello: dict[str, Any]) -> None:
        """Initialize the live runtime for a newly negotiated session."""

    async def handle_client_message(
        self,
        session: "SessionContext",
        message: dict[str, Any],
        sender: "SessionSender",
    ) -> None:
        """Consume a validated client message after coordinator-level checks."""

    async def close(self, session: "SessionContext") -> None:
        """Tear down any live resources for the session."""


class SessionStateBackend(Protocol):
    """State seam for future lifecycle tracking and resumability."""

    async def on_connected(self, session: "SessionContext", client: str) -> None:
        """Persist session state after the websocket is accepted."""

    async def on_hello(self, session: "SessionContext", hello: dict[str, Any]) -> None:
        """Persist negotiated hello metadata."""

    async def on_client_message(self, session: "SessionContext", message: dict[str, Any]) -> None:
        """Observe validated client traffic."""

    async def on_disconnected(self, session: "SessionContext", reason: str) -> None:
        """Persist final session state."""


class ToolRouter(Protocol):
    """Tool seam for future model tool calls and look/agent dispatch."""

    async def bind(self, session: "SessionContext", sender: "SessionSender") -> None:
        """Prepare tool routing for an active session."""

    async def close(self, session: "SessionContext") -> None:
        """Release tool routing resources for the session."""


class SessionSender(Protocol):
    async def send(self, payload: dict[str, Any]) -> None:
        """Send a server message to the websocket client."""


@dataclass(slots=True)
class SessionContext:
    session_id: str = field(default_factory=lambda: f"session-{uuid4().hex}")
    resume_token: str = field(default_factory=lambda: f"resume-{uuid4().hex}")
    resumed: bool = False
    lifecycle_state: SessionLifecycleState = field(default_factory=SessionLifecycleState)


class NullLiveAdapter:
    """Compile-friendly adapter until the Gemini Live bridge lands."""

    model_name = "coordinator-stub"

    async def open(self, session: SessionContext, hello: dict[str, Any]) -> None:
        log.info(
            "session live adapter open session_id=%s client=%s",
            session.session_id,
            hello.get("client", "unknown"),
        )

    async def handle_client_message(
        self,
        session: SessionContext,
        message: dict[str, Any],
        sender: SessionSender,
    ) -> None:
        log.info(
            "session live adapter queued session_id=%s type=%s",
            session.session_id,
            message.get("type", "?"),
        )

    async def close(self, session: SessionContext) -> None:
        log.info("session live adapter close session_id=%s", session.session_id)


class InMemorySessionStateBackend:
    """Minimal state seam until the owned state machine module exists."""

    async def on_connected(self, session: SessionContext, client: str) -> None:
        log.info("session state connected session_id=%s client=%s", session.session_id, client)

    async def on_hello(self, session: SessionContext, hello: dict[str, Any]) -> None:
        log.info(
            "session state negotiated session_id=%s resume_requested=%s",
            session.session_id,
            bool(hello.get("session_resume")),
        )

    async def on_client_message(self, session: SessionContext, message: dict[str, Any]) -> None:
        log.debug(
            "session state observed session_id=%s type=%s",
            session.session_id,
            message.get("type", "?"),
        )

    async def on_disconnected(self, session: SessionContext, reason: str) -> None:
        log.info("session state disconnected session_id=%s reason=%s", session.session_id, reason)


class NullToolRouter:
    """Compile-friendly tool seam until model function routing exists."""

    async def bind(self, session: SessionContext, sender: SessionSender) -> None:
        log.debug("session tool router bound session_id=%s", session.session_id)

    async def close(self, session: SessionContext) -> None:
        log.debug("session tool router closed session_id=%s", session.session_id)


class WebSocketSessionSender:
    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws

    async def send(self, payload: dict[str, Any]) -> None:
        await self._ws.send_text(json.dumps(payload))


class SessionCoordinator:
    """Owns the websocket session loop and delegates to future subsystems."""

    def __init__(
        self,
        *,
        live_adapter: LiveAdapter | None = None,
        state_backend: SessionStateBackend | None = None,
        tool_router: ToolRouter | None = None,
    ) -> None:
        self._live_adapter = live_adapter or self._build_default_live_adapter()
        self._state_backend = state_backend or InMemorySessionStateBackend()
        self._tool_router = tool_router or NullToolRouter()

    async def run(self, ws: WebSocket) -> None:
        await ws.accept()
        client = self._client_label(ws)
        session = SessionContext()
        sender = WebSocketSessionSender(ws)
        disconnect_reason = "client_disconnect"

        log.info("session connected session_id=%s client=%s", session.session_id, client)
        await self._state_backend.on_connected(session, client)
        await self._tool_router.bind(session, sender)

        try:
            while True:
                raw = await ws.receive_text()
                try:
                    message = parse_client_message(raw)
                except ProtocolError as exc:
                    await sender.send(exc.to_server_error().to_payload())
                    continue

                await self._handle_message(session, message, sender)
        except WebSocketDisconnect:
            log.info("session disconnected session_id=%s client=%s", session.session_id, client)
        except Exception as exc:  # noqa: BLE001
            disconnect_reason = "server_error"
            log.exception("session error session_id=%s client=%s: %s", session.session_id, client, exc)
            try:
                await self._send_error(sender, "internal_error", "internal session error", fatal=True)
                await ws.close(code=1011)
            except RuntimeError:
                pass
        finally:
            await self._tool_router.close(session)
            await self._live_adapter.close(session)
            await self._state_backend.on_disconnected(session, disconnect_reason)

    async def _handle_message(
        self,
        session: SessionContext,
        message: ClientMessage,
        sender: SessionSender,
    ) -> None:
        message_payload = asdict(message)
        message_type = message_payload["type"]

        try:
            next_state = session.lifecycle_state.transition(message)
        except StateTransitionError as exc:
            await sender.send(exc.to_server_error().to_payload())
            return

        log.info("session received session_id=%s type=%s", session.session_id, message_type)
        session.lifecycle_state = next_state

        if isinstance(message, HelloMessage):
            await self._handle_hello(session, message, sender)
            return

        await self._state_backend.on_client_message(session, message_payload)

        if message_type == "ping":
            await sender.send(
                {
                    "type": "pong",
                    "ts_ms_client": message.ts_ms,
                    "ts_ms_server": self._timestamp_ms(),
                }
            )
            return

        await self._live_adapter.handle_client_message(session, message_payload, sender)

    async def _handle_hello(
        self,
        session: SessionContext,
        hello: HelloMessage,
        sender: SessionSender,
    ) -> None:
        hello_payload = asdict(hello)
        session.resumed = bool(hello.session_resume)

        await self._state_backend.on_hello(session, hello_payload)
        await self._live_adapter.open(session, hello_payload)

        await sender.send(
            {
                "type": "ready",
                "session_id": session.session_id,
                "session_resume_token": session.resume_token,
                "resumed": session.resumed,
                "model": self._live_adapter.model_name,
            }
        )

    @staticmethod
    def _build_default_live_adapter() -> LiveAdapter:
        from .live_adapter import build_live_adapter

        return build_live_adapter()

    @staticmethod
    def _client_label(ws: WebSocket) -> str:
        if ws.client is None:
            return "unknown"
        return f"{ws.client.host}:{ws.client.port}"

    @staticmethod
    def _timestamp_ms() -> int:
        return int(time.time() * 1000)

    @staticmethod
    async def _send_error(
        sender: SessionSender,
        code: str,
        message: str,
        *,
        fatal: bool | None = None,
    ) -> None:
        await sender.send(error_payload(code, message, fatal=fatal))
