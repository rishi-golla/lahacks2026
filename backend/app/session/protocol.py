"""Typed websocket protocol utilities for the session endpoint."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from enum import StrEnum
from typing import Any, TypeAlias


class ClientMessageType(StrEnum):
    HELLO = "hello"
    AUDIO = "audio"
    AUDIO_END = "audio_end"
    PHOTO = "photo"
    TEXT = "text"
    BARGE_IN = "barge_in"
    PING = "ping"


class DeviceKind(StrEnum):
    IPHONE_MOCK = "iphone-mock"
    IPHONE_REAL = "iphone-real"
    IPHONE_NO_GLASSES = "iphone-no-glasses"


class PhotoTrigger(StrEnum):
    AUTO = "auto"
    USER_REQUEST = "user_request"
    TOOL_LOOK = "tool_look"


class ProtocolErrorCode(StrEnum):
    INVALID_JSON = "invalid_json"
    INVALID_MESSAGE = "invalid_message"
    UNKNOWN_TYPE = "unknown_type"
    MISSING_FIELD = "missing_field"
    INVALID_FIELD = "invalid_field"
    PROTOCOL_VIOLATION = "protocol_violation"


@dataclass(slots=True, frozen=True)
class Capabilities:
    audio_in: bool
    audio_out: bool
    photo: bool
    barge_in: bool

    @classmethod
    def from_dict(cls, raw: Any) -> Capabilities:
        data = _expect_mapping(raw, field_name="capabilities")
        return cls(
            audio_in=_expect_bool(data, "audio_in"),
            audio_out=_expect_bool(data, "audio_out"),
            photo=_expect_bool(data, "photo"),
            barge_in=_expect_bool(data, "barge_in"),
        )


@dataclass(slots=True, frozen=True)
class HelloMessage:
    client: str
    client_version: str
    device: DeviceKind
    session_resume: str | None
    capabilities: Capabilities
    type: ClientMessageType = field(default=ClientMessageType.HELLO, init=False)


@dataclass(slots=True, frozen=True)
class AudioFrame:
    pcm_b64: str
    sample_rate: int
    ts_ms: int | None = None
    type: ClientMessageType = field(default=ClientMessageType.AUDIO, init=False)


@dataclass(slots=True, frozen=True)
class AudioEndMessage:
    type: ClientMessageType = field(default=ClientMessageType.AUDIO_END, init=False)


@dataclass(slots=True, frozen=True)
class PhotoFrame:
    jpeg_b64: str
    trigger: PhotoTrigger
    tool_call_id: str | None
    ts_ms: int
    type: ClientMessageType = field(default=ClientMessageType.PHOTO, init=False)


@dataclass(slots=True, frozen=True)
class TextInputMessage:
    text: str
    type: ClientMessageType = field(default=ClientMessageType.TEXT, init=False)


@dataclass(slots=True, frozen=True)
class BargeInMessage:
    type: ClientMessageType = field(default=ClientMessageType.BARGE_IN, init=False)


@dataclass(slots=True, frozen=True)
class PingMessage:
    ts_ms: int
    type: ClientMessageType = field(default=ClientMessageType.PING, init=False)


ClientMessage: TypeAlias = (
    HelloMessage
    | AudioFrame
    | AudioEndMessage
    | PhotoFrame
    | TextInputMessage
    | BargeInMessage
    | PingMessage
)


@dataclass(slots=True, frozen=True)
class ServerErrorMessage:
    message: str
    code: ProtocolErrorCode | str | None = None
    fatal: bool | None = None
    details: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": "error", "message": self.message}
        if self.code is not None:
            payload["code"] = str(self.code)
        if self.fatal is not None:
            payload["fatal"] = self.fatal
        if self.details:
            payload["details"] = self.details
        return payload


@dataclass(slots=True, frozen=True)
class ProtocolError(Exception):
    code: ProtocolErrorCode
    message: str
    fatal: bool = False
    details: dict[str, Any] | None = None

    def to_server_error(self) -> ServerErrorMessage:
        return ServerErrorMessage(
            message=self.message,
            code=self.code,
            fatal=self.fatal,
            details=self.details,
        )


def parse_client_message(raw: str | bytes | bytearray | dict[str, Any]) -> ClientMessage:
    data = _coerce_message_dict(raw)
    raw_type = data.get("type")
    if not isinstance(raw_type, str) or not raw_type:
        raise ProtocolError(
            code=ProtocolErrorCode.MISSING_FIELD,
            message="client message is missing a string type",
            details={"field": "type"},
        )

    try:
        message_type = ClientMessageType(raw_type)
    except ValueError as exc:
        raise ProtocolError(
            code=ProtocolErrorCode.UNKNOWN_TYPE,
            message=f"unsupported client message type: {raw_type}",
            details={"type": raw_type},
        ) from exc

    if message_type is ClientMessageType.HELLO:
        return _parse_hello(data)
    if message_type is ClientMessageType.AUDIO:
        return _parse_audio(data)
    if message_type is ClientMessageType.AUDIO_END:
        return AudioEndMessage()
    if message_type is ClientMessageType.PHOTO:
        return _parse_photo(data)
    if message_type is ClientMessageType.TEXT:
        return _parse_text(data)
    if message_type is ClientMessageType.BARGE_IN:
        return BargeInMessage()
    if message_type is ClientMessageType.PING:
        return _parse_ping(data)

    raise AssertionError(f"unhandled message type: {message_type}")


def error_payload(
    code: ProtocolErrorCode | str,
    message: str,
    *,
    fatal: bool | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ServerErrorMessage(
        message=message,
        code=code,
        fatal=fatal,
        details=details,
    ).to_payload()


def _coerce_message_dict(raw: str | bytes | bytearray | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw

    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError(
                code=ProtocolErrorCode.INVALID_JSON,
                message="client message must be valid UTF-8 JSON",
            ) from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProtocolError(
            code=ProtocolErrorCode.INVALID_JSON,
            message="client message must be valid JSON",
        ) from exc

    if not isinstance(parsed, dict):
        raise ProtocolError(
            code=ProtocolErrorCode.INVALID_MESSAGE,
            message="client message must decode to a JSON object",
        )
    return parsed


def _parse_hello(data: dict[str, Any]) -> HelloMessage:
    client = data.get("client", "ios")
    if not isinstance(client, str) or not client:
        raise _invalid_field("client", "client must be a non-empty string")

    session_resume = data.get("session_resume")
    if session_resume is not None and not isinstance(session_resume, str):
        raise _invalid_field("session_resume", "session_resume must be a string when present")

    device_raw = _expect_str(data, "device")
    try:
        device = DeviceKind(device_raw)
    except ValueError as exc:
        raise _invalid_field("device", f"unsupported device: {device_raw}") from exc

    return HelloMessage(
        client=client,
        client_version=_expect_str(data, "client_version"),
        device=device,
        session_resume=session_resume,
        capabilities=Capabilities.from_dict(data.get("capabilities")),
    )


def _parse_audio(data: dict[str, Any]) -> AudioFrame:
    sample_rate = _expect_int(data, "sample_rate")
    if sample_rate <= 0:
        raise _invalid_field("sample_rate", "sample_rate must be greater than zero")

    ts_ms = data.get("ts_ms")
    if ts_ms is not None and not isinstance(ts_ms, int):
        raise _invalid_field("ts_ms", "ts_ms must be an integer when present")

    pcm_b64 = _expect_str(data, "pcm_b64")
    if not pcm_b64.strip():
        raise _invalid_field("pcm_b64", "pcm_b64 must be a non-empty string")

    return AudioFrame(
        pcm_b64=pcm_b64,
        sample_rate=sample_rate,
        ts_ms=ts_ms,
    )


def _parse_photo(data: dict[str, Any]) -> PhotoFrame:
    trigger_raw = _expect_str(data, "trigger")
    try:
        trigger = PhotoTrigger(trigger_raw)
    except ValueError as exc:
        raise _invalid_field("trigger", f"unsupported trigger: {trigger_raw}") from exc

    tool_call_id = data.get("tool_call_id")
    if tool_call_id is not None and not isinstance(tool_call_id, str):
        raise _invalid_field("tool_call_id", "tool_call_id must be a string when present")

    jpeg_b64 = _expect_str(data, "jpeg_b64")
    if not jpeg_b64.strip():
        raise _invalid_field("jpeg_b64", "jpeg_b64 must be a non-empty string")

    return PhotoFrame(
        jpeg_b64=jpeg_b64,
        trigger=trigger,
        tool_call_id=tool_call_id,
        ts_ms=_expect_int(data, "ts_ms"),
    )


def _parse_text(data: dict[str, Any]) -> TextInputMessage:
    text = _expect_str(data, "text")
    if not text.strip():
        raise _invalid_field("text", "text must be a non-empty string")
    return TextInputMessage(text=text)


def _parse_ping(data: dict[str, Any]) -> PingMessage:
    return PingMessage(ts_ms=_expect_int(data, "ts_ms"))


def _expect_mapping(raw: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise _invalid_field(field_name, f"{field_name} must be an object")
    return raw


def _expect_str(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if value is None:
        raise ProtocolError(
            code=ProtocolErrorCode.MISSING_FIELD,
            message=f"client message is missing required field: {field_name}",
            details={"field": field_name},
        )
    if not isinstance(value, str):
        raise _invalid_field(field_name, f"{field_name} must be a string")
    return value


def _expect_int(data: dict[str, Any], field_name: str) -> int:
    value = data.get(field_name)
    if value is None:
        raise ProtocolError(
            code=ProtocolErrorCode.MISSING_FIELD,
            message=f"client message is missing required field: {field_name}",
            details={"field": field_name},
        )
    if isinstance(value, bool) or not isinstance(value, int):
        raise _invalid_field(field_name, f"{field_name} must be an integer")
    return value


def _expect_bool(data: dict[str, Any], field_name: str) -> bool:
    value = data.get(field_name)
    if isinstance(value, bool):
        return value
    if value is None:
        raise ProtocolError(
            code=ProtocolErrorCode.MISSING_FIELD,
            message=f"client message is missing required field: {field_name}",
            details={"field": field_name},
        )
    raise _invalid_field(field_name, f"{field_name} must be a boolean")


def _invalid_field(field_name: str, message: str) -> ProtocolError:
    return ProtocolError(
        code=ProtocolErrorCode.INVALID_FIELD,
        message=message,
        details={"field": field_name},
    )
