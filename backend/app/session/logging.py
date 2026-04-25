"""Structured, replay-safe logging helpers for live sessions.

This module is intentionally standalone so future session components can share a
common event taxonomy and payload summarization strategy without logging raw
multimodal content.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from enum import Enum, StrEnum
import json
import logging
from typing import Any

JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | dict[str, "JSONValue"] | list["JSONValue"]

_TEXT_PREVIEW_LIMIT = 120
_MAX_COLLECTION_ITEMS = 8
_MAX_DEPTH = 6
_RAW_STRING_KEYS = {"type", "id", "name", "mime_type", "role", "status"}
_MEDIA_KEY_MARKERS = {
    "audio": "audio",
    "pcm": "audio",
    "wav": "audio",
    "image": "image",
    "jpeg": "image",
    "jpg": "image",
    "png": "image",
    "frame": "image",
    "video": "video",
    "blob": "binary",
    "bytes": "binary",
    "base64": "binary",
    "data": "binary",
    "chunk": "binary",
}


class EventCategory(StrEnum):
    SESSION = "session"
    PROTOCOL = "protocol"
    GEMINI = "gemini"
    TOOL = "tool"


class SessionLifecycleEvent(StrEnum):
    CONNECT_REQUESTED = "session.connect.requested"
    CONNECTED = "session.connected"
    ACCEPTED = "session.accepted"
    RESUMED = "session.resumed"
    DISCONNECT_REQUESTED = "session.disconnect.requested"
    DISCONNECTED = "session.disconnected"
    CLOSED = "session.closed"
    ERROR = "session.error"


class ProtocolEvent(StrEnum):
    CLIENT_MESSAGE_RECEIVED = "protocol.client.message.received"
    CLIENT_MESSAGE_REJECTED = "protocol.client.message.rejected"
    CLIENT_MESSAGE_SENT = "protocol.client.message.sent"
    SERVER_MESSAGE_RECEIVED = "protocol.server.message.received"
    SERVER_MESSAGE_SENT = "protocol.server.message.sent"
    PARSE_FAILED = "protocol.parse.failed"
    TURN_STARTED = "protocol.turn.started"
    TURN_COMPLETED = "protocol.turn.completed"


class GeminiEvent(StrEnum):
    CONNECT_REQUESTED = "gemini.connect.requested"
    CONNECTED = "gemini.connected"
    SETUP_COMPLETED = "gemini.setup.completed"
    INPUT_SENT = "gemini.input.sent"
    RESPONSE_RECEIVED = "gemini.response.received"
    TOOL_CALL_RECEIVED = "gemini.tool_call.received"
    TOOL_RESPONSE_SENT = "gemini.tool_response.sent"
    GOAWAY_RECEIVED = "gemini.goaway.received"
    RESUMPTION_UPDATED = "gemini.resumption.updated"
    INTERRUPTED = "gemini.interrupted"
    CLOSED = "gemini.closed"
    ERROR = "gemini.error"


class ToolEvent(StrEnum):
    DISPATCHED = "tool.dispatched"
    STARTED = "tool.started"
    SUCCEEDED = "tool.succeeded"
    FAILED = "tool.failed"
    TIMED_OUT = "tool.timed_out"
    RESPONSE_SENT = "tool.response.sent"


def log_event(
    logger: logging.Logger,
    event: StrEnum | str,
    *,
    category: EventCategory | str,
    level: int = logging.INFO,
    payload: Any | None = None,
    error: BaseException | None = None,
    session_id: str | None = None,
    connection_id: str | None = None,
    **fields: Any,
) -> dict[str, JSONValue]:
    """Log a structured event as a single JSON line and return the record."""

    record = build_event(
        event,
        category=category,
        payload=payload,
        error=error,
        session_id=session_id,
        connection_id=connection_id,
        **fields,
    )
    logger.log(level, json.dumps(record, sort_keys=True, separators=(",", ":")))
    return record


def build_event(
    event: StrEnum | str,
    *,
    category: EventCategory | str,
    payload: Any | None = None,
    error: BaseException | None = None,
    session_id: str | None = None,
    connection_id: str | None = None,
    **fields: Any,
) -> dict[str, JSONValue]:
    """Build a replay-safe event payload without emitting a log line."""

    record: dict[str, JSONValue] = {
        "schema": "live_session_event.v1",
        "timestamp": _utc_now(),
        "event": _enum_value(event),
        "category": _enum_value(category),
    }
    if session_id is not None:
        record["session_id"] = session_id
    if connection_id is not None:
        record["connection_id"] = connection_id
    if payload is not None:
        record["payload_summary"] = summarize_payload(payload)
    if error is not None:
        record["error"] = summarize_exception(error)

    for key, value in fields.items():
        record[key] = _normalize_context_value(value)

    return record


def summarize_protocol_message(payload: Any) -> JSONValue:
    return summarize_payload(payload)


def summarize_gemini_message(payload: Any) -> JSONValue:
    return summarize_payload(payload)


def summarize_tool_call(payload: Any) -> JSONValue:
    return summarize_payload(payload)


def summarize_exception(error: BaseException) -> dict[str, JSONValue]:
    return {
        "type": error.__class__.__name__,
        "message": _truncate_text(str(error), limit=_TEXT_PREVIEW_LIMIT),
    }


def summarize_payload(payload: Any, *, _depth: int = 0, _key: str | None = None) -> JSONValue:
    if _depth >= _MAX_DEPTH:
        return {"summary": "max_depth_reached"}

    media_kind = _media_kind_for_key(_key)
    if _should_redact_scalar(payload, media_kind):
        return _redacted_summary(payload, media_kind or "binary")

    if isinstance(payload, Enum):
        return _enum_value(payload)

    if payload is None or isinstance(payload, bool | int | float):
        return payload

    if isinstance(payload, str):
        if _key in _RAW_STRING_KEYS and len(payload) <= _TEXT_PREVIEW_LIMIT:
            return payload
        return _summarize_string(payload, media_kind)

    if isinstance(payload, bytes | bytearray | memoryview):
        return _redacted_summary(payload, media_kind or "binary")

    if isinstance(payload, Mapping):
        return _summarize_mapping(payload, depth=_depth)

    if isinstance(payload, Sequence) and not isinstance(payload, str | bytes | bytearray | memoryview):
        return _summarize_sequence(payload, depth=_depth, key=_key)

    return {"repr": _truncate_text(repr(payload), limit=_TEXT_PREVIEW_LIMIT)}


def _summarize_mapping(payload: Mapping[Any, Any], *, depth: int) -> dict[str, JSONValue]:
    summary: dict[str, JSONValue] = {}
    items = list(payload.items())
    for index, (raw_key, value) in enumerate(items):
        if index >= _MAX_COLLECTION_ITEMS:
            summary["_truncated_items"] = len(items) - _MAX_COLLECTION_ITEMS
            break
        key = str(raw_key)
        summary[key] = summarize_payload(value, _depth=depth + 1, _key=key)
    return summary


def _summarize_sequence(
    payload: Sequence[Any],
    *,
    depth: int,
    key: str | None,
) -> list[JSONValue]:
    media_kind = _media_kind_for_key(key)
    if media_kind is not None:
        return [_redacted_summary(payload, media_kind)]

    items = list(payload[:_MAX_COLLECTION_ITEMS])
    summary = [summarize_payload(item, _depth=depth + 1) for item in items]
    if len(payload) > _MAX_COLLECTION_ITEMS:
        summary.append({"_truncated_items": len(payload) - _MAX_COLLECTION_ITEMS})
    return summary


def _summarize_string(value: str, media_kind: str | None) -> JSONValue:
    if media_kind is not None and _looks_binary_text(value):
        return _redacted_summary(value, media_kind)

    return {
        "chars": len(value),
        "preview": _truncate_text(value, limit=_TEXT_PREVIEW_LIMIT),
    }


def _normalize_context_value(value: Any) -> JSONValue:
    if isinstance(value, Enum):
        return _enum_value(value)
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, BaseException):
        return summarize_exception(value)
    return summarize_payload(value)


def _redacted_summary(value: Any, kind: str) -> dict[str, JSONValue]:
    size = len(value) if hasattr(value, "__len__") else None
    summary: dict[str, JSONValue] = {
        "redacted": True,
        "kind": kind,
    }
    if size is not None:
        summary["size"] = size
    return summary


def _should_redact_scalar(value: Any, media_kind: str | None) -> bool:
    if media_kind is None:
        return False
    return isinstance(value, str | bytes | bytearray | memoryview | Sequence)


def _media_kind_for_key(key: str | None) -> str | None:
    if not key:
        return None

    normalized = key.replace("-", "_").lower()
    for marker, kind in _MEDIA_KEY_MARKERS.items():
        if marker in normalized:
            return kind
    return None


def _looks_binary_text(value: str) -> bool:
    if len(value) >= 48:
        return True
    return "\u0000" in value


def _truncate_text(value: str, *, limit: int) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 1]}..."


def _enum_value(value: Enum | str) -> str:
    return value.value if isinstance(value, Enum) else value


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
