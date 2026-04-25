"""State machine for websocket client message sequencing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .protocol import ClientMessage, ClientMessageType, HelloMessage, ProtocolError, ProtocolErrorCode


class SessionPhase(StrEnum):
    AWAITING_HELLO = "awaiting_hello"
    READY = "ready"
    RECEIVING_AUDIO = "receiving_audio"
    CLOSED = "closed"


@dataclass(slots=True, frozen=True)
class SessionLifecycleState:
    phase: SessionPhase = SessionPhase.AWAITING_HELLO
    hello: HelloMessage | None = None

    def transition(self, message: ClientMessage) -> SessionLifecycleState:
        message_type = message.type

        if self.phase is SessionPhase.CLOSED:
            raise StateTransitionError(
                message=f"cannot process {message_type} after session is closed",
                details={"state": self.phase, "type": message_type},
            )

        if message_type is ClientMessageType.PING:
            return self

        if self.phase is SessionPhase.AWAITING_HELLO:
            if message_type is ClientMessageType.HELLO:
                return SessionLifecycleState(phase=SessionPhase.READY, hello=message)
            raise StateTransitionError(
                message=f"{message_type} is not allowed before hello",
                details={"state": self.phase, "type": message_type, "expected": "hello"},
            )

        if self.phase is SessionPhase.READY:
            if message_type is ClientMessageType.HELLO:
                raise StateTransitionError(
                    message="duplicate hello is not allowed after the session is ready",
                    details={"state": self.phase, "type": message_type},
                )
            if message_type is ClientMessageType.AUDIO:
                return SessionLifecycleState(phase=SessionPhase.RECEIVING_AUDIO, hello=self.hello)
            if message_type in {
                ClientMessageType.TEXT,
                ClientMessageType.PHOTO,
                ClientMessageType.BARGE_IN,
                ClientMessageType.AUDIO_END,
            }:
                if message_type is ClientMessageType.AUDIO_END:
                    raise StateTransitionError(
                        message="audio_end is only allowed after one or more audio frames",
                        details={"state": self.phase, "type": message_type},
                    )
                return self

        if self.phase is SessionPhase.RECEIVING_AUDIO:
            if message_type is ClientMessageType.AUDIO:
                return self
            if message_type is ClientMessageType.AUDIO_END:
                return SessionLifecycleState(phase=SessionPhase.READY, hello=self.hello)
            if message_type in {
                ClientMessageType.PHOTO,
                ClientMessageType.TEXT,
                ClientMessageType.BARGE_IN,
            }:
                return self
            raise StateTransitionError(
                message=f"{message_type} is not allowed while an audio turn is in progress",
                details={
                    "state": self.phase,
                    "type": message_type,
                    "expected": "audio|audio_end|photo|text|barge_in|ping",
                },
            )

        raise AssertionError(f"unhandled session phase: {self.phase}")

    def close(self) -> SessionLifecycleState:
        return SessionLifecycleState(phase=SessionPhase.CLOSED, hello=self.hello)


class StateTransitionError(ProtocolError):
    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(
            code=ProtocolErrorCode.PROTOCOL_VIOLATION,
            message=message,
            fatal=False,
            details=details,
        )
