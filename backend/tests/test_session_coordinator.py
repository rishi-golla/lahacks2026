from __future__ import annotations

import base64
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from fastapi import WebSocketDisconnect

from app.session.coordinator import SessionCoordinator
from app.session.resume_store import InMemoryResumeStore, RestoreOutcome, TurnStateSnapshot


_FIXTURE_JPEG = (Path(__file__).parent / "fixtures" / "one_pixel.jpg").read_bytes()
_FIXTURE_JPEG_B64 = base64.b64encode(_FIXTURE_JPEG).decode()


class SessionCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_photo_dump_writes_received_jpeg_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = _FakeWebSocket(
                [
                    _message(
                        {
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
                    ),
                    _message(
                        {
                            "type": "photo",
                            "jpeg_b64": _FIXTURE_JPEG_B64,
                            "trigger": "user_request",
                            "ts_ms": 123,
                        }
                    ),
                ]
            )

            await SessionCoordinator(live_adapter=_LookAdapter(), photo_dump_dir=tmpdir).run(ws)

            dumped_files = list(Path(tmpdir).glob("session-*/*.jpg"))
            self.assertEqual(len(dumped_files), 1)
            self.assertEqual(dumped_files[0].name, "123-user_request.jpg")
            self.assertEqual(dumped_files[0].read_bytes(), _FIXTURE_JPEG)

    async def test_tool_look_photo_is_correlated_before_reaching_adapter(self) -> None:
        adapter = _LookAdapter()
        store = InMemoryResumeStore()
        ws = _FakeWebSocket(
            [
                _message(
                    {
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
                ),
                _message({"type": "text", "text": "please look again"}),
                _message(
                    {
                        "type": "photo",
                        "jpeg_b64": "/9j/",
                        "trigger": "tool_look",
                        "tool_call_id": "tool-1",
                        "ts_ms": 456,
                    }
                ),
            ]
        )

        await SessionCoordinator(live_adapter=adapter, resume_store=store).run(ws)

        sent = [_json(payload) for payload in ws.sent_texts]
        self.assertEqual(sent[1], {"type": "look_request", "tool_call_id": "tool-1", "reason": "Need fresh visual context"})
        self.assertEqual(sent[2], {"type": "ack"})
        self.assertIsNotNone(adapter.received_photo)
        assert adapter.received_photo is not None
        self.assertEqual(adapter.received_photo["look_request"]["tool_call_id"], "tool-1")
        self.assertEqual(adapter.received_photo["look_request"]["state"], "fulfilled")

        record = store.get(sent[0]["session_id"])
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.turn_state.last_client_message_type, "photo")
        self.assertEqual(record.turn_state.last_server_event_type, "look_request")

    async def test_resume_store_restore_and_token_rotation_are_coordinator_managed(self) -> None:
        store = InMemoryResumeStore()
        store.upsert_session(
            "session-restore",
            "resume-1",
            turn_state=TurnStateSnapshot(phase="ready", turn_id="turn-1"),
            resumable=True,
        )
        ws = _FakeWebSocket(
            [
                _message(
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
                ),
                _message({"type": "text", "text": "continue"}),
            ]
        )

        await SessionCoordinator(
            live_adapter=_ResumeAdapter(next_token="resume-2"),
            resume_store=store,
        ).run(ws)

        sent = [_json(payload) for payload in ws.sent_texts]
        self.assertEqual(sent[0]["type"], "ready")
        self.assertEqual(sent[0]["session_id"], "session-restore")
        self.assertEqual(sent[0]["session_resume_token"], "resume-1")
        self.assertTrue(sent[0]["resumed"])
        self.assertEqual(sent[1], {"type": "session_update", "session_resume_token": "resume-2"})

        restored = store.restore("resume-1")
        self.assertEqual(restored.outcome, RestoreOutcome.RESTORED)
        self.assertIsNotNone(restored.session)
        assert restored.session is not None
        self.assertEqual(restored.session.resume_token, "resume-2")
        self.assertEqual(restored.session.turn_state.turn_id, "turn-1")
        self.assertEqual(restored.session.turn_state.last_client_message_type, "text")

        disconnected = store.get("session-restore")
        self.assertIsNotNone(disconnected)
        assert disconnected is not None
        self.assertIsNotNone(disconnected.disconnected_at)
        self.assertIsNotNone(disconnected.expires_at)


class _LookAdapter:
    model_name = "look-adapter"

    def __init__(self) -> None:
        self.received_photo: dict[str, object] | None = None

    async def open(self, session, hello, sender=None) -> None:
        return None

    async def handle_client_message(self, session, message, sender) -> None:
        if message["type"] == "text":
            await sender.send_look_request(
                tool_call_id="tool-1",
                reason="Need fresh visual context",
            )
            return
        self.received_photo = message
        await sender.send({"type": "ack"})

    async def close(self, session) -> None:
        return None


class _ResumeAdapter:
    model_name = "resume-adapter"

    def __init__(self, *, next_token: str) -> None:
        self._next_token = next_token

    async def open(self, session, hello, sender=None) -> None:
        return None

    async def handle_client_message(self, session, message, sender) -> None:
        sender.record_server_event("transcript_out", turn_id="turn-1", resumable=True)
        await sender.send_session_update(
            session_resume_token=self._next_token,
            resumable=True,
        )

    async def close(self, session) -> None:
        return None


class _FakeWebSocket:
    def __init__(self, inbound_messages: list[str]) -> None:
        self.client = SimpleNamespace(host="127.0.0.1", port=9000)
        self._inbound_messages = list(inbound_messages)
        self.sent_texts: list[str] = []
        self.accepted = False
        self.closed_code: int | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def receive_text(self) -> str:
        if not self._inbound_messages:
            raise WebSocketDisconnect()
        return self._inbound_messages.pop(0)

    async def send_text(self, payload: str) -> None:
        self.sent_texts.append(payload)

    async def close(self, code: int) -> None:
        self.closed_code = code


def _message(payload: dict[str, object]) -> str:
    return json.dumps(payload)


def _json(payload: str) -> dict[str, object]:
    return json.loads(payload)


if __name__ == "__main__":
    unittest.main()
