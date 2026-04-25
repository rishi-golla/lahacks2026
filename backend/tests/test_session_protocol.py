from __future__ import annotations

import unittest

from app.session.protocol import (
    AudioEndMessage,
    AudioFrame,
    BargeInMessage,
    ClientMessageType,
    DeviceKind,
    HelloMessage,
    PhotoFrame,
    PhotoTrigger,
    PingMessage,
    ProtocolError,
    ProtocolErrorCode,
    TextInputMessage,
    error_payload,
    parse_client_message,
)


class SessionProtocolTests(unittest.TestCase):
    def test_parse_hello_message(self) -> None:
        message = parse_client_message(
            {
                "type": "hello",
                "client": "ios",
                "client_version": "0.1.0",
                "device": "iphone-mock",
                "session_resume": "resume-1",
                "capabilities": {
                    "audio_in": True,
                    "audio_out": True,
                    "photo": True,
                    "barge_in": True,
                },
            }
        )

        self.assertEqual(
            message,
            HelloMessage(
                client="ios",
                client_version="0.1.0",
                device=DeviceKind.IPHONE_MOCK,
                session_resume="resume-1",
                capabilities=message.capabilities,
            ),
        )

    def test_parse_other_message_types(self) -> None:
        cases = [
            (
                {"type": "audio", "pcm_b64": "AAE=", "sample_rate": 16000, "ts_ms": 10},
                AudioFrame(pcm_b64="AAE=", sample_rate=16000, ts_ms=10),
            ),
            ({"type": "audio_end"}, AudioEndMessage()),
            (
                {
                    "type": "photo",
                    "jpeg_b64": "/9j/",
                    "trigger": "tool_look",
                    "tool_call_id": "tool-1",
                    "ts_ms": 11,
                },
                PhotoFrame(
                    jpeg_b64="/9j/",
                    trigger=PhotoTrigger.TOOL_LOOK,
                    tool_call_id="tool-1",
                    ts_ms=11,
                ),
            ),
            ({"type": "text", "text": "hello"}, TextInputMessage(text="hello")),
            ({"type": "barge_in"}, BargeInMessage()),
            ({"type": "ping", "ts_ms": 12}, PingMessage(ts_ms=12)),
        ]

        for payload, expected in cases:
            with self.subTest(message_type=payload["type"]):
                self.assertEqual(parse_client_message(payload), expected)

    def test_parse_invalid_json_raises_protocol_error(self) -> None:
        with self.assertRaises(ProtocolError) as ctx:
            parse_client_message("{")

        self.assertEqual(ctx.exception.code, ProtocolErrorCode.INVALID_JSON)

    def test_parse_unknown_type_raises_protocol_error(self) -> None:
        with self.assertRaises(ProtocolError) as ctx:
            parse_client_message({"type": "future"})

        self.assertEqual(ctx.exception.code, ProtocolErrorCode.UNKNOWN_TYPE)
        self.assertEqual(ctx.exception.details, {"type": "future"})

    def test_parse_missing_field_raises_protocol_error(self) -> None:
        with self.assertRaises(ProtocolError) as ctx:
            parse_client_message({"type": "ping"})

        self.assertEqual(ctx.exception.code, ProtocolErrorCode.MISSING_FIELD)
        self.assertEqual(ctx.exception.details, {"field": "ts_ms"})

    def test_parse_invalid_field_raises_protocol_error(self) -> None:
        with self.assertRaises(ProtocolError) as ctx:
            parse_client_message({"type": "audio", "pcm_b64": "AAE=", "sample_rate": 0})

        self.assertEqual(ctx.exception.code, ProtocolErrorCode.INVALID_FIELD)
        self.assertEqual(ctx.exception.details, {"field": "sample_rate"})

    def test_error_payload_is_structured(self) -> None:
        payload = error_payload(
            ProtocolErrorCode.PROTOCOL_VIOLATION,
            "audio_end is only allowed after audio",
            fatal=False,
            details={"state": "ready", "type": ClientMessageType.AUDIO_END},
        )

        self.assertEqual(
            payload,
            {
                "type": "error",
                "code": "protocol_violation",
                "message": "audio_end is only allowed after audio",
                "fatal": False,
                "details": {"state": "ready", "type": ClientMessageType.AUDIO_END},
            },
        )


if __name__ == "__main__":
    unittest.main()
