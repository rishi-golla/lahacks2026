"""Session coordination for the `/session` WebSocket.

This module owns the client-facing session loop while keeping integration seams
lightweight for the upcoming Gemini Live bridge, session state machine, and
tool-routing work.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
from dataclasses import asdict, replace
import json
import logging
from pathlib import Path
import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect

from .event_mapper import EventMapperState, complete_output_turn, map_server_event
from .look_loop import LookLoop, LookRequest, UnknownLookRequestError
from .protocol import (
    ClientMessage,
    HelloMessage,
    PhotoFrame,
    PhotoTrigger,
    ProtocolError,
    error_payload,
    parse_client_message,
)
from .resume_store import InMemoryResumeStore, RestoreOutcome, TurnStateSnapshot
from .settings import BACKEND_ROOT, get_session_settings
from .state import SessionLifecycleState, StateTransitionError

log = logging.getLogger(__name__)


class LiveAdapter(Protocol):
    """Bridge between the websocket session and the live model runtime."""

    model_name: str

    async def open(
        self,
        session: "SessionContext",
        hello: dict[str, Any],
        sender: "SessionSender",
    ) -> None:
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

    async def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        """Map a backend event onto the wire contract and send it."""

    async def complete_output_turn(self) -> None:
        """Advance mapper state after a model turn ends without a wire message."""

    async def send_look_request(
        self,
        *,
        tool_call_id: str,
        reason: str,
        timeout_ms: int | None = None,
    ) -> LookRequest:
        """Track and emit a tool-driven look request."""

    async def send_session_update(
        self,
        *,
        session_resume_token: str,
        turn_state: TurnStateSnapshot | None = None,
        resumable: bool | None = None,
    ) -> None:
        """Publish a new session resume token and persist it."""

    def record_server_event(
        self,
        event_type: str,
        *,
        phase: str | None = None,
        turn_id: str | None = None,
        response_id: str | None = None,
        resumable: bool | None = None,
    ) -> TurnStateSnapshot:
        """Record server-side state used for resumability snapshots."""

    def fail_look_request(self, tool_call_id: str, reason: str) -> LookRequest:
        """Resolve a pending look request as failed."""

    def cancel_look_request(self, tool_call_id: str, reason: str = "look request cancelled") -> LookRequest:
        """Resolve a pending look request as cancelled."""

    async def flush_pending(self) -> None:
        """Flush any buffered outbound events once the session is ready."""


@dataclass(slots=True)
class SessionContext:
    session_id: str = field(default_factory=lambda: f"session-{uuid4().hex}")
    resume_token: str = field(default_factory=lambda: f"resume-{uuid4().hex}")
    resumed: bool = False
    lifecycle_state: SessionLifecycleState = field(default_factory=SessionLifecycleState)
    look_loop: LookLoop = field(default_factory=LookLoop)
    turn_state: TurnStateSnapshot = field(
        default_factory=lambda: TurnStateSnapshot(phase="awaiting_hello")
    )
    restore_outcome: RestoreOutcome | None = None


class NullLiveAdapter:
    """Compile-friendly adapter until the Gemini Live bridge lands."""

    model_name = "coordinator-stub"

    async def open(
        self,
        session: SessionContext,
        hello: dict[str, Any],
        sender: SessionSender,
    ) -> None:
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
    def __init__(
        self,
        ws: WebSocket,
        *,
        session: SessionContext,
        coordinator: "SessionCoordinator",
    ) -> None:
        self._ws = ws
        self._session = session
        self._coordinator = coordinator
        self._mapper_state = EventMapperState()
        self._send_lock = asyncio.Lock()
        self._pending_payloads: list[dict[str, Any]] = []
        self._ready_for_events = False

    async def send(self, payload: dict[str, Any]) -> None:
        async with self._send_lock:
            await self._ws.send_text(json.dumps(payload))

    async def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        mapped_payload, next_state = map_server_event(event_type, payload, self._mapper_state)
        self._mapper_state = next_state
        if not self._ready_for_events:
            self._pending_payloads.append(mapped_payload)
            return
        await self.send(mapped_payload)

    async def complete_output_turn(self) -> None:
        self._mapper_state = complete_output_turn(self._mapper_state)

    async def send_look_request(
        self,
        *,
        tool_call_id: str,
        reason: str,
        timeout_ms: int | None = None,
    ) -> LookRequest:
        request = self._session.look_loop.create_request(
            tool_call_id=tool_call_id,
            reason=reason,
            requested_at_ms=self._coordinator._timestamp_ms(),
            timeout_ms=timeout_ms,
        )
        self._coordinator._update_turn_state(
            self._session,
            phase="waiting_for_tool_look",
            last_server_event_type="look_request",
        )
        self._coordinator._persist_resume_state(self._session, resumable=False)
        await self.emit("look_request", request.to_client_payload())
        return request

    async def send_session_update(
        self,
        *,
        session_resume_token: str,
        turn_state: TurnStateSnapshot | None = None,
        resumable: bool | None = None,
    ) -> None:
        self._session.resume_token = session_resume_token
        if turn_state is not None:
            self._session.turn_state = turn_state
        self._coordinator._persist_resume_state(self._session, resumable=resumable)
        await self.emit(
            "session_update",
            {"session_resume_token": self._session.resume_token},
        )

    def record_server_event(
        self,
        event_type: str,
        *,
        phase: str | None = None,
        turn_id: str | None = None,
        response_id: str | None = None,
        resumable: bool | None = None,
    ) -> TurnStateSnapshot:
        turn_state = self._coordinator._update_turn_state(
            self._session,
            phase=phase,
            turn_id=turn_id,
            response_id=response_id,
            last_server_event_type=event_type,
        )
        self._coordinator._persist_resume_state(self._session, resumable=resumable)
        return turn_state

    def fail_look_request(self, tool_call_id: str, reason: str) -> LookRequest:
        request = self._session.look_loop.fail_request(tool_call_id, reason)
        self._coordinator._update_turn_state(
            self._session,
            phase="ready",
            last_server_event_type="look_request_failed",
        )
        self._coordinator._persist_resume_state(self._session)
        return request

    def cancel_look_request(self, tool_call_id: str, reason: str = "look request cancelled") -> LookRequest:
        request = self._session.look_loop.cancel_request(tool_call_id, reason)
        self._coordinator._update_turn_state(
            self._session,
            phase="ready",
            last_server_event_type="look_request_cancelled",
        )
        self._coordinator._persist_resume_state(self._session)
        return request

    async def flush_pending(self) -> None:
        self._ready_for_events = True
        while self._pending_payloads:
            await self.send(self._pending_payloads.pop(0))


_DEFAULT_RESUME_STORE = InMemoryResumeStore()


class SessionCoordinator:
    """Owns the websocket session loop and delegates to future subsystems."""

    def __init__(
        self,
        *,
        live_adapter: LiveAdapter | None = None,
        state_backend: SessionStateBackend | None = None,
        tool_router: ToolRouter | None = None,
        resume_store: InMemoryResumeStore | None = None,
        photo_dump_dir: str | Path | None = None,
    ) -> None:
        self._live_adapter = live_adapter or self._build_default_live_adapter()
        self._state_backend = state_backend or InMemorySessionStateBackend()
        self._tool_router = tool_router or NullToolRouter()
        self._resume_store = resume_store or _DEFAULT_RESUME_STORE
        configured_photo_dump_dir = (
            Path(photo_dump_dir) if photo_dump_dir is not None else self._configured_photo_dump_dir()
        )
        self._photo_dump_dir = configured_photo_dump_dir

    async def run(self, ws: WebSocket) -> None:
        await ws.accept()
        client = self._client_label(ws)
        session = SessionContext()
        sender = WebSocketSessionSender(ws, session=session, coordinator=self)
        disconnect_reason = "client_disconnect"

        log.info("session connected session_id=%s client=%s", session.session_id, client)
        await self._state_backend.on_connected(session, client)
        await self._tool_router.bind(session, sender)

        try:
            while True:
                self._expire_pending_look_requests(session)
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
            if self._resume_store.get(session.session_id) is not None:
                self._resume_store.mark_disconnected(
                    session.session_id,
                    turn_state=session.turn_state,
                    resumable=self._is_resumable(session),
                )
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

        if message_type == "audio":
            log.debug("session received session_id=%s type=%s", session.session_id, message_type)
        else:
            log.info("session received session_id=%s type=%s", session.session_id, message_type)
        if isinstance(message, PhotoFrame):
            log.info(
                "session received photo session_id=%s trigger=%s tool_call_id=%s b64_chars=%s ts_ms=%s",
                session.session_id,
                message.trigger.value,
                message.tool_call_id,
                len(message.jpeg_b64),
                message.ts_ms,
            )
            self._dump_photo_if_enabled(session, message)
        session.lifecycle_state = next_state

        if isinstance(message, HelloMessage):
            await self._handle_hello(session, message, sender)
            return

        if isinstance(message, PhotoFrame) and message.trigger is PhotoTrigger.TOOL_LOOK:
            try:
                resolved = session.look_loop.complete_request(message)
                log.info(
                    "session completed look_request session_id=%s tool_call_id=%s photo_b64_chars=%s photo_ts_ms=%s",
                    session.session_id,
                    resolved.tool_call_id,
                    len(resolved.photo_jpeg_b64 or ""),
                    resolved.photo_ts_ms,
                )
            except (UnknownLookRequestError, ValueError) as exc:
                log.warning(
                    "session failed look_request photo correlation session_id=%s tool_call_id=%s error=%s",
                    session.session_id,
                    message.tool_call_id,
                    exc,
                )
                await self._send_error(
                    sender,
                    "protocol_violation",
                    str(exc),
                    details={"type": "photo", "tool_call_id": message.tool_call_id},
                )
                return
            message_payload["look_request"] = self._serialize_look_request(resolved)

        self._update_turn_state(
            session,
            phase=self._phase_for_lifecycle(session),
            last_client_message_type=message_type,
        )
        await self._state_backend.on_client_message(session, message_payload)
        self._persist_resume_state(session)

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
        self._restore_session_from_hello(session, hello)
        hello_payload["resume_restore_outcome"] = (
            session.restore_outcome.value if session.restore_outcome is not None else None
        )

        await self._state_backend.on_hello(session, hello_payload)
        await self._open_live_adapter(session, hello_payload, sender)
        self._update_turn_state(session, phase=self._phase_for_lifecycle(session))
        self._persist_resume_state(session)

        await sender.send(
            {
                "type": "ready",
                "session_id": session.session_id,
                "session_resume_token": session.resume_token,
                "resumed": session.resumed,
                "model": self._live_adapter.model_name,
            }
        )
        await sender.flush_pending()

    @staticmethod
    def _build_default_live_adapter() -> LiveAdapter:
        from .live_adapter import build_live_adapter

        return build_live_adapter()

    @staticmethod
    def _configured_photo_dump_dir() -> Path | None:
        dump_dir = get_session_settings().session_photo_dump_dir
        if not dump_dir:
            return None
        path = Path(dump_dir)
        if not path.is_absolute():
            path = BACKEND_ROOT / path
        return path

    def _dump_photo_if_enabled(self, session: SessionContext, photo: PhotoFrame) -> None:
        if self._photo_dump_dir is None:
            return

        try:
            photo_bytes = base64.b64decode(photo.jpeg_b64, validate=True)
        except binascii.Error:
            log.warning(
                "session photo dump skipped invalid base64 session_id=%s trigger=%s ts_ms=%s",
                session.session_id,
                photo.trigger.value,
                photo.ts_ms,
            )
            return

        dump_dir = self._photo_dump_dir / session.session_id
        dump_dir.mkdir(parents=True, exist_ok=True)
        safe_trigger = "".join(
            character if character.isalnum() or character in {"-", "_"} else "_"
            for character in photo.trigger.value
        )
        path = dump_dir / f"{photo.ts_ms}-{safe_trigger}.jpg"
        path.write_bytes(photo_bytes)
        digest = hashlib.sha256(photo_bytes).hexdigest()
        first_bytes = photo_bytes[:12].hex(" ")
        metadata_path = path.with_suffix(".json")
        metadata_path.write_text(
            json.dumps(
                {
                    "session_id": session.session_id,
                    "trigger": photo.trigger.value,
                    "tool_call_id": photo.tool_call_id,
                    "ts_ms": photo.ts_ms,
                    "bytes": len(photo_bytes),
                    "base64_chars": len(photo.jpeg_b64),
                    "sha256": digest,
                    "first_bytes_hex": first_bytes,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        log.info(
            "session dumped photo session_id=%s path=%s bytes=%s sha256=%s first_bytes=%s",
            session.session_id,
            path,
            len(photo_bytes),
            digest,
            first_bytes,
        )

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
        details: dict[str, Any] | None = None,
    ) -> None:
        await sender.send(error_payload(code, message, fatal=fatal, details=details))

    def _restore_session_from_hello(self, session: SessionContext, hello: HelloMessage) -> None:
        requested_token = hello.session_resume
        if not requested_token:
            session.resumed = False
            session.restore_outcome = RestoreOutcome.UNKNOWN
            return

        session.resumed = True
        restored = self._resume_store.restore(requested_token)
        session.restore_outcome = restored.outcome
        if restored.outcome is not RestoreOutcome.RESTORED or restored.session is None:
            return

        record = restored.session
        session.session_id = record.session_id
        session.resume_token = record.resume_token
        session.turn_state = record.turn_state

    async def _open_live_adapter(
        self,
        session: SessionContext,
        hello_payload: dict[str, Any],
        sender: SessionSender,
    ) -> None:
        try:
            await self._live_adapter.open(session, hello_payload, sender)
        except TypeError:
            await self._live_adapter.open(session, hello_payload)

    def _persist_resume_state(
        self,
        session: SessionContext,
        *,
        resumable: bool | None = None,
    ) -> None:
        self._resume_store.upsert_session(
            session.session_id,
            session.resume_token,
            turn_state=session.turn_state,
            resumable=self._is_resumable(session) if resumable is None else resumable,
        )

    def _update_turn_state(
        self,
        session: SessionContext,
        *,
        phase: str | None = None,
        turn_id: str | None = None,
        response_id: str | None = None,
        last_client_message_type: str | None = None,
        last_server_event_type: str | None = None,
    ) -> TurnStateSnapshot:
        current = session.turn_state
        session.turn_state = replace(
            current,
            phase=current.phase if phase is None else phase,
            turn_id=current.turn_id if turn_id is None else turn_id,
            response_id=current.response_id if response_id is None else response_id,
            last_client_message_type=(
                current.last_client_message_type
                if last_client_message_type is None
                else last_client_message_type
            ),
            last_server_event_type=(
                current.last_server_event_type
                if last_server_event_type is None
                else last_server_event_type
            ),
        )
        return session.turn_state

    def _expire_pending_look_requests(self, session: SessionContext) -> None:
        expired = session.look_loop.expire_requests(now_ms=self._timestamp_ms())
        if not expired:
            return
        self._update_turn_state(
            session,
            phase="ready",
            last_server_event_type="look_request_timed_out",
        )
        self._persist_resume_state(session)

    @staticmethod
    def _serialize_look_request(request: LookRequest) -> dict[str, Any]:
        return {
            "tool_call_id": request.tool_call_id,
            "reason": request.reason,
            "requested_at_ms": request.requested_at_ms,
            "timeout_ms": request.timeout_ms,
            "deadline_ms": request.deadline_ms,
            "state": request.state.value,
            "photo_ts_ms": request.photo_ts_ms,
            "failure_reason": request.failure_reason,
        }

    @staticmethod
    def _phase_for_lifecycle(session: SessionContext) -> str:
        if session.look_loop.pending_tool_call_ids():
            return "waiting_for_tool_look"
        return str(session.lifecycle_state.phase)

    @staticmethod
    def _is_resumable(session: SessionContext) -> bool:
        return (
            not session.look_loop.pending_tool_call_ids()
            and str(session.lifecycle_state.phase) == "ready"
        )
