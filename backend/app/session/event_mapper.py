"""Pure helpers for mapping backend session events to the iOS wire contract."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping


ServerPayload = dict[str, Any]
SourcePayload = Mapping[str, Any] | object


@dataclass(frozen=True)
class EventMapperState:
    """Immutable mapper state used to synthesize turn IDs when upstream omits them."""

    active_turn_id: str | None = None
    next_turn_index: int = 1


@dataclass(frozen=True)
class _ReadyEvent:
    session_id: str
    model: str
    session_resume_token: str | None = None
    resumed: bool = False

    def to_payload(self) -> ServerPayload:
        payload: ServerPayload = {
            "type": "ready",
            "session_id": self.session_id,
            "resumed": self.resumed,
            "model": self.model,
        }
        if self.session_resume_token is not None:
            payload["session_resume_token"] = self.session_resume_token
        return payload


@dataclass(frozen=True)
class _SessionUpdateEvent:
    session_resume_token: str

    def to_payload(self) -> ServerPayload:
        return {
            "type": "session_update",
            "session_resume_token": self.session_resume_token,
        }


@dataclass(frozen=True)
class _TranscriptInEvent:
    text: str
    is_final: bool = False
    timestamp_ms: int | None = None

    def to_payload(self) -> ServerPayload:
        payload: ServerPayload = {
            "type": "transcript_in",
            "text": self.text,
            "is_final": self.is_final,
        }
        if self.timestamp_ms is not None:
            payload["ts_ms"] = self.timestamp_ms
        return payload


@dataclass(frozen=True)
class _TranscriptOutEvent:
    text: str
    turn_id: str
    is_final: bool = False

    def to_payload(self) -> ServerPayload:
        return {
            "type": "transcript_out",
            "text": self.text,
            "turn_id": self.turn_id,
            "is_final": self.is_final,
        }


@dataclass(frozen=True)
class _AudioChunkEvent:
    pcm_b64: str
    turn_id: str
    sample_rate: int = 24_000

    def to_payload(self) -> ServerPayload:
        return {
            "type": "audio_chunk",
            "pcm_b64": self.pcm_b64,
            "sample_rate": self.sample_rate,
            "turn_id": self.turn_id,
        }


@dataclass(frozen=True)
class _LookRequestEvent:
    tool_call_id: str
    reason: str

    def to_payload(self) -> ServerPayload:
        return {
            "type": "look_request",
            "tool_call_id": self.tool_call_id,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class _ModelInterruptEvent:
    turn_id: str

    def to_payload(self) -> ServerPayload:
        return {
            "type": "model_interrupt",
            "turn_id": self.turn_id,
        }


@dataclass(frozen=True)
class _SessionEndEvent:
    reason: str

    def to_payload(self) -> ServerPayload:
        return {
            "type": "session_end",
            "reason": self.reason,
        }


def map_server_event(
    event_type: str,
    payload: SourcePayload | None = None,
    state: EventMapperState | None = None,
) -> tuple[ServerPayload, EventMapperState]:
    """Dispatch a supported backend event into the iOS server-message shape."""

    normalized_state = state or EventMapperState()
    source = _coerce_mapping(payload)

    if event_type == "ready":
        return map_ready_event(source, normalized_state)
    if event_type == "session_update":
        return map_session_update_event(source, normalized_state)
    if event_type == "transcript_in":
        return map_transcript_in_event(source, normalized_state)
    if event_type == "transcript_out":
        return map_transcript_out_event(source, normalized_state)
    if event_type == "audio_chunk":
        return map_audio_chunk_event(source, normalized_state)
    if event_type == "look_request":
        return map_look_request_event(source, normalized_state)
    if event_type == "model_interrupt":
        return map_model_interrupt_event(source, normalized_state)
    if event_type == "session_end":
        return map_session_end_event(source, normalized_state)

    raise ValueError(f"unsupported server event type: {event_type}")


def map_ready_event(
    payload: SourcePayload | None = None,
    state: EventMapperState | None = None,
) -> tuple[ServerPayload, EventMapperState]:
    source = _coerce_mapping(payload)
    event = _ReadyEvent(
        session_id=_require_str(source, "session_id", "sessionId"),
        session_resume_token=_optional_str(
            source,
            "session_resume_token",
            "sessionResumeToken",
            "resume_token",
        ),
        resumed=_optional_bool(source, "resumed", "is_resumed", "isResumed", default=False),
        model=_require_str(source, "model", "model_name", "modelName"),
    )
    return event.to_payload(), state or EventMapperState()


def map_session_update_event(
    payload: SourcePayload | None = None,
    state: EventMapperState | None = None,
) -> tuple[ServerPayload, EventMapperState]:
    source = _coerce_mapping(payload)
    event = _SessionUpdateEvent(
        session_resume_token=_require_str(
            source,
            "session_resume_token",
            "sessionResumeToken",
            "resume_token",
        )
    )
    return event.to_payload(), state or EventMapperState()


def map_transcript_in_event(
    payload: SourcePayload | None = None,
    state: EventMapperState | None = None,
) -> tuple[ServerPayload, EventMapperState]:
    source = _coerce_mapping(payload)
    event = _TranscriptInEvent(
        text=_require_str(source, "text", "transcript"),
        is_final=_resolve_finality(source),
        timestamp_ms=_optional_int(source, "ts_ms", "timestamp_ms", "timestampMs"),
    )
    return event.to_payload(), state or EventMapperState()


def map_transcript_out_event(
    payload: SourcePayload | None = None,
    state: EventMapperState | None = None,
) -> tuple[ServerPayload, EventMapperState]:
    source = _coerce_mapping(payload)
    payload_state = state or EventMapperState()
    turn_id, next_state = _resolve_turn_id(
        source,
        payload_state,
        "turn_id",
        "turnId",
    )
    event = _TranscriptOutEvent(
        text=_require_str(source, "text", "transcript"),
        turn_id=turn_id,
        is_final=_resolve_finality(source),
    )
    return event.to_payload(), next_state


def map_audio_chunk_event(
    payload: SourcePayload | None = None,
    state: EventMapperState | None = None,
) -> tuple[ServerPayload, EventMapperState]:
    source = _coerce_mapping(payload)
    payload_state = state or EventMapperState()
    turn_id, next_state = _resolve_turn_id(
        source,
        payload_state,
        "turn_id",
        "turnId",
    )
    event = _AudioChunkEvent(
        pcm_b64=_require_str(source, "pcm_b64", "pcmBase64", "audio"),
        sample_rate=_optional_int(source, "sample_rate", "sampleRate", default=24_000),
        turn_id=turn_id,
    )
    return event.to_payload(), next_state


def map_look_request_event(
    payload: SourcePayload | None = None,
    state: EventMapperState | None = None,
) -> tuple[ServerPayload, EventMapperState]:
    source = _coerce_mapping(payload)
    event = _LookRequestEvent(
        tool_call_id=_require_str(source, "tool_call_id", "toolCallId"),
        reason=_require_str(source, "reason", "prompt", "message"),
    )
    return event.to_payload(), state or EventMapperState()


def map_model_interrupt_event(
    payload: SourcePayload | None = None,
    state: EventMapperState | None = None,
) -> tuple[ServerPayload, EventMapperState]:
    source = _coerce_mapping(payload)
    payload_state = state or EventMapperState()
    turn_id, next_state = _resolve_turn_id(
        source,
        payload_state,
        "turn_id",
        "turnId",
    )
    event = _ModelInterruptEvent(turn_id=turn_id)
    return event.to_payload(), next_state


def map_session_end_event(
    payload: SourcePayload | None = None,
    state: EventMapperState | None = None,
) -> tuple[ServerPayload, EventMapperState]:
    source = _coerce_mapping(payload)
    event = _SessionEndEvent(reason=_require_str(source, "reason", "message"))
    return event.to_payload(), state or EventMapperState()


def _coerce_mapping(payload: SourcePayload | None) -> Mapping[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, Mapping):
        return payload
    if hasattr(payload, "__dict__"):
        values = vars(payload)
        if isinstance(values, dict):
            return values
    raise TypeError(f"event payload must be a mapping or object, got {type(payload)!r}")


def _resolve_turn_id(
    source: Mapping[str, Any],
    state: EventMapperState,
    *keys: str,
) -> tuple[str, EventMapperState]:
    existing = _optional_str(source, *keys)
    if existing:
        return existing, replace(state, active_turn_id=existing)
    if state.active_turn_id:
        return state.active_turn_id, state

    turn_id = f"turn-{state.next_turn_index:04d}"
    next_state = replace(
        state,
        active_turn_id=turn_id,
        next_turn_index=state.next_turn_index + 1,
    )
    return turn_id, next_state


def _resolve_finality(source: Mapping[str, Any]) -> bool:
    value = _optional_value(source, "is_final", "final", "finality", "complete")
    if value is None:
        return False
    return bool(value)


def _require_str(source: Mapping[str, Any], *keys: str) -> str:
    value = _optional_value(source, *keys)
    if value is None:
        joined = ", ".join(keys)
        raise ValueError(f"missing required field; expected one of: {joined}")
    return str(value)


def _optional_str(source: Mapping[str, Any], *keys: str) -> str | None:
    value = _optional_value(source, *keys)
    if value is None:
        return None
    return str(value)


def _optional_int(source: Mapping[str, Any], *keys: str, default: int | None = None) -> int | None:
    value = _optional_value(source, *keys)
    if value is None:
        return default
    return int(value)


def _optional_bool(
    source: Mapping[str, Any],
    *keys: str,
    default: bool | None = None,
) -> bool:
    value = _optional_value(source, *keys)
    if value is None:
        if default is None:
            raise ValueError(f"missing boolean field for keys: {', '.join(keys)}")
        return default
    return bool(value)


def _optional_value(source: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in source:
            return source[key]
    return None
