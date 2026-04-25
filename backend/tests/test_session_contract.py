from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.session.coordinator import SessionCoordinator


class SessionContractTests(unittest.TestCase):
    def test_ping_is_supported_before_hello_and_hello_still_required_for_readiness(self) -> None:
        with _session_socket() as websocket:
            websocket.send_json({"type": "ping", "ts_ms": 123})

            pong = websocket.receive_json()
            self.assertEqual(pong["type"], "pong")
            self.assertEqual(pong["ts_ms_client"], 123)
            self.assertIsInstance(pong["ts_ms_server"], int)

            websocket.send_json(_hello_payload())

            ready = websocket.receive_json()
            self.assertEqual(ready["type"], "ready")

    def test_ready_message_matches_ios_contract_shape(self) -> None:
        with _session_socket() as websocket:
            websocket.send_json(_hello_payload(session_resume="resume-from-client"))

            ready = websocket.receive_json()

        self.assertEqual(
            set(ready),
            {"type", "session_id", "session_resume_token", "resumed", "model"},
        )
        self.assertEqual(ready["type"], "ready")
        self.assertTrue(ready["session_id"].startswith("session-"))
        self.assertTrue(ready["session_resume_token"].startswith("resume-"))
        self.assertTrue(ready["resumed"])
        self.assertEqual(ready["model"], "echo")

    def test_invalid_json_returns_protocol_error_and_connection_stays_open(self) -> None:
        with _session_socket() as websocket:
            websocket.send_text("{")

            error = websocket.receive_json()
            self.assertEqual(
                error,
                {
                    "type": "error",
                    "code": "invalid_json",
                    "message": "client message must be valid JSON",
                    "fatal": False,
                },
            )

            websocket.send_json(_hello_payload())

            ready = websocket.receive_json()
            self.assertEqual(ready["type"], "ready")

    def test_content_before_hello_returns_protocol_violation(self) -> None:
        with _session_socket() as websocket:
            websocket.send_json({"type": "text", "text": "hello too soon"})

            self.assertEqual(
                websocket.receive_json(),
                {
                    "type": "error",
                    "code": "protocol_violation",
                    "message": "text is not allowed before hello",
                    "fatal": False,
                    "details": {
                        "state": "awaiting_hello",
                        "type": "text",
                        "expected": "hello",
                    },
                },
            )

    def test_audio_end_before_audio_returns_protocol_violation_after_handshake(self) -> None:
        with _session_socket() as websocket:
            websocket.send_json(_hello_payload())
            self.assertEqual(websocket.receive_json()["type"], "ready")

            websocket.send_json({"type": "audio_end"})

            self.assertEqual(
                websocket.receive_json(),
                {
                    "type": "error",
                    "code": "protocol_violation",
                    "message": "audio_end is only allowed after one or more audio frames",
                    "fatal": False,
                    "details": {
                        "state": "ready",
                        "type": "audio_end",
                    },
                },
            )

    def test_post_handshake_text_is_echoed_by_current_coordinator_backend(self) -> None:
        with _session_socket() as websocket:
            websocket.send_json(_hello_payload())
            self.assertEqual(websocket.receive_json()["type"], "ready")

            payload = {"type": "text", "text": "hello backend"}
            websocket.send_json(payload)

            self.assertEqual(
                websocket.receive_json(),
                {
                    "type": "echo",
                    "received": payload,
                },
            )


def _hello_payload(*, session_resume: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": "hello",
        "client": "ios",
        "client_version": "0.1.0",
        "device": "iphone-mock",
        "capabilities": {
            "audio_in": True,
            "audio_out": True,
            "photo": True,
            "barge_in": True,
        },
    }
    if session_resume is not None:
        payload["session_resume"] = session_resume
    return payload


def _session_socket():
    adapter = _EchoAdapter()
    patcher = patch.object(SessionCoordinator, "_build_default_live_adapter", return_value=adapter)
    patcher.start()
    client = TestClient(app)
    client.__enter__()
    websocket = client.websocket_connect("/session")
    websocket.__enter__()

    class _SocketContext:
        def __enter__(self):
            return websocket

        def __exit__(self, exc_type, exc, tb) -> None:
            websocket.__exit__(exc_type, exc, tb)
            client.__exit__(exc_type, exc, tb)
            patcher.stop()

    return _SocketContext()


class _EchoAdapter:
    model_name = "echo"

    async def open(self, session, hello) -> None:
        return None

    async def handle_client_message(self, session, message, sender) -> None:
        await sender.send({"type": "echo", "received": message})

    async def close(self, session) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
