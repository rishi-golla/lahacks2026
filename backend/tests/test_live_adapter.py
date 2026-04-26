from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from typing import Any
import unittest
from unittest.mock import AsyncMock, patch

from app.session.coordinator import SessionContext
from app.google.models import LinkedGoogleUser
from app.google.store import google_state_store
from app.session.live_adapter import GeminiLiveAdapter
from app.session.settings import LiveBackend, SessionSettings


class GeminiLiveAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        google_state_store.reset()

    def test_settings_parse_comma_separated_response_modalities(self) -> None:
        settings = SessionSettings.model_validate(
            {
                "live_backend": LiveBackend.GEMINI,
                "gemini_api_key": "test-key",
                "gemini_response_modalities": "TEXT,AUDIO",
            }
        )

        self.assertEqual(settings.gemini_response_modalities, ("TEXT", "AUDIO"))

    def test_settings_parse_plain_response_modality_from_env(self) -> None:
        old_env = os.environ.copy()
        try:
            os.environ["LIVE_BACKEND"] = "gemini"
            os.environ["GEMINI_API_KEY"] = "test-key"
            os.environ["GEMINI_RESPONSE_MODALITIES"] = "TEXT"

            settings = SessionSettings()

            self.assertEqual(settings.gemini_response_modalities, ("TEXT",))
        finally:
            os.environ.clear()
            os.environ.update(old_env)

    async def test_text_messages_are_forwarded_as_realtime_input(self) -> None:
        session = _FakeGeminiSession()
        client = _FakeGenaiClient(session)
        adapter = _build_adapter(session, client=client)
        sender = _FakeSender()

        await adapter.open(SessionContext(), _hello_payload(), sender)
        await adapter.handle_client_message(
            SessionContext(),
            {"type": "text", "text": "hello gemini"},
            sender,
        )

        self.assertEqual(session.realtime_input_calls, [{"text": "hello gemini"}])
        self.assertEqual(client.aio.live.connected_configs[-1].response_modalities, ["TEXT"])
        self.assertIsNone(client.aio.live.connected_configs[-1].input_audio_transcription)
        self.assertIsNone(client.aio.live.connected_configs[-1].output_audio_transcription)

    async def test_audio_response_modality_enables_transcription_configs(self) -> None:
        session = _FakeGeminiSession()
        client = _FakeGenaiClient(session)
        adapter = _build_adapter(session, client=client, response_modalities=("AUDIO",))
        sender = _FakeSender()

        await adapter.open(SessionContext(), _hello_payload(), sender)

        config = client.aio.live.connected_configs[-1]
        self.assertEqual(config.response_modalities, ["AUDIO"])
        self.assertIsNotNone(config.input_audio_transcription)
        self.assertIsNotNone(config.output_audio_transcription)

    async def test_live_connect_includes_google_search_tool_when_enabled(self) -> None:
        session = _FakeGeminiSession()
        client = _FakeGenaiClient(session)
        adapter = _build_adapter(session, client=client, google_search_grounding=True)
        sender = _FakeSender()

        await adapter.open(SessionContext(), _hello_payload(), sender)

        config = client.aio.live.connected_configs[-1]
        self.assertEqual(len(config.tools), 2)
        self.assertIsNotNone(config.tools[0].google_search)
        self.assertIsNotNone(config.tools[1].function_declarations)
        self.assertIn("built-in Google Search", config.system_instruction)

    async def test_live_connect_omits_google_search_tool_when_disabled(self) -> None:
        session = _FakeGeminiSession()
        client = _FakeGenaiClient(session)
        adapter = _build_adapter(session, client=client, google_search_grounding=False)
        sender = _FakeSender()

        await adapter.open(SessionContext(), _hello_payload(), sender)

        config = client.aio.live.connected_configs[-1]
        self.assertEqual(len(config.tools), 1)
        self.assertIsNone(getattr(config.tools[0], "google_search", None))
        self.assertIsNotNone(config.tools[0].function_declarations)
        self.assertNotIn("built-in Google Search", config.system_instruction)

    async def test_audio_messages_are_forwarded_as_realtime_audio(self) -> None:
        session = _FakeGeminiSession()
        adapter = _build_adapter(session)
        sender = _FakeSender()

        await adapter.open(SessionContext(), _hello_payload(), sender)
        await adapter.handle_client_message(
            SessionContext(),
            {"type": "audio", "pcm_b64": "AAE=", "sample_rate": 16000, "ts_ms": 10},
            sender,
        )

        self.assertEqual(len(session.realtime_input_calls), 1)
        self.assertEqual(session.realtime_input_calls[0]["audio"].data, b"\x00\x01")
        self.assertEqual(
            session.realtime_input_calls[0]["audio"].mime_type,
            "audio/pcm;rate=16000",
        )

    async def test_audio_end_messages_close_the_realtime_audio_stream(self) -> None:
        session = _FakeGeminiSession()
        adapter = _build_adapter(session)
        sender = _FakeSender()

        await adapter.open(SessionContext(), _hello_payload(), sender)
        await adapter.handle_client_message(
            SessionContext(),
            {"type": "audio_end"},
            sender,
        )

        self.assertEqual(session.realtime_input_calls, [{"audio_stream_end": True}])

    async def test_photo_messages_are_forwarded_as_realtime_video(self) -> None:
        session = _FakeGeminiSession()
        adapter = _build_adapter(session)
        sender = _FakeSender()

        await adapter.open(SessionContext(), _hello_payload(), sender)
        await adapter.handle_client_message(
            SessionContext(),
            {
                "type": "photo",
                "jpeg_b64": "/9j/",
                "trigger": "user_request",
                "tool_call_id": "tool-1",
                "ts_ms": 42,
            },
            sender,
        )

        self.assertEqual(len(session.realtime_input_calls), 1)
        self.assertEqual(session.realtime_input_calls[0]["video"].data, b"\xff\xd8\xff")
        self.assertEqual(session.realtime_input_calls[0]["video"].mime_type, "image/jpeg")

    async def test_unavailable_live_session_returns_nonfatal_error(self) -> None:
        sender = _FakeSender()
        adapter = _build_adapter(_FakeGeminiSession())

        await adapter.handle_client_message(
            SessionContext(),
            {"type": "text", "text": "hello"},
            sender,
        )

        self.assertEqual(
            sender.messages,
            [
                {
                    "type": "error",
                    "code": "live_session_unavailable",
                    "message": "Gemini Live session is not connected",
                    "fatal": False,
                }
            ],
        )

    async def test_unsupported_message_types_return_warning(self) -> None:
        session = _FakeGeminiSession()
        sender = _FakeSender()
        adapter = _build_adapter(session)

        await adapter.open(SessionContext(), _hello_payload(), sender)
        await adapter.handle_client_message(
            SessionContext(),
            {"type": "barge_in"},
            sender,
        )

        self.assertEqual(sender.messages, [])

    # ------------------------------------------------------------------
    # Agent tool call tests
    # ------------------------------------------------------------------

    async def test_agent_tool_call_dispatches_to_omegaclaw_and_sends_function_response(self) -> None:
        session = _FakeGeminiSession()
        sender = _FakeSender()
        adapter = _build_adapter(session)
        await adapter.open(SessionContext(), _hello_payload(), sender)

        fut: asyncio.Future[dict] = asyncio.get_running_loop().create_future()
        fut.set_result({"result": {"summary": "Alice is a software engineer at Acme."}})

        mock_loop = AsyncMock()
        mock_loop.run_once = AsyncMock(return_value=True)
        adapter._agent_loop = mock_loop

        with patch("app.session.live_adapter._omegaclaw_enqueue", return_value=("req-1", fut)), \
             patch("app.session.live_adapter._omegaclaw_available", True):
            response = _live_response_with_tool_call(
                "call-1", "agent",
                {"intent": "who is this", "name": "Alice", "organization": "Acme", "title": "Engineer"},
            )
            await adapter._handle_server_message(response, sender)
            await asyncio.sleep(0)

        self.assertEqual(len(session.tool_response_calls), 1)
        fn_resp = session.tool_response_calls[0][0]
        self.assertEqual(fn_resp.id, "call-1")
        self.assertEqual(fn_resp.name, "agent")
        self.assertIn("started that for you", fn_resp.response["output"].lower())
        mock_loop.run_once.assert_awaited()

    async def test_agent_tool_call_uses_backend_channel_submit_when_available(self) -> None:
        session = _FakeGeminiSession()
        sender = _FakeSender()
        adapter = _build_adapter(session)
        adapter._backend_channel = AsyncMock()
        adapter._backend_channel.submit = AsyncMock(
            return_value={
                "summary": "Alice is a software engineer at Acme.",
                "confidence": "high",
                "source": "agentverse:identify_person",
            }
        )
        request_session = SessionContext(session_id="session-backend-channel")
        await adapter.open(request_session, _hello_payload(), sender)

        response = _live_response_with_tool_call(
            "call-backend-channel",
            "agent",
            {
                "intent": "identify_person",
                "name": "Alice",
                "organization": "Acme",
                "title": "Engineer",
            },
        )
        await adapter._handle_server_message(response, sender, request_session)
        await asyncio.sleep(0)

        adapter._backend_channel.submit.assert_awaited_once()
        task = adapter._backend_channel.submit.await_args.args[0]
        self.assertEqual(task.session_id, "session-backend-channel")
        self.assertEqual(task.turn_id, "call-backend-channel")
        self.assertEqual(task.intent, "identify_person")
        self.assertEqual(task.tool_call_id, "call-backend-channel")
        self.assertEqual(
            task.args,
            {"name": "Alice", "organization": "Acme", "title": "Engineer"},
        )
        self.assertEqual(len(session.tool_response_calls), 1)
        output = session.tool_response_calls[0][0].response["output"]
        self.assertIn("started that for you", output.lower())

    async def test_agent_tool_call_sends_started_and_result_tool_events_to_ios(self) -> None:
        session = _FakeGeminiSession()
        sender = _FakeSender()
        adapter = _build_adapter(session)
        await adapter.open(SessionContext(), _hello_payload(), sender)

        fut: asyncio.Future[dict] = asyncio.get_running_loop().create_future()
        fut.set_result({"result": {"summary": "Bob is a product manager."}})

        mock_loop = AsyncMock()
        mock_loop.run_once = AsyncMock(return_value=True)
        adapter._agent_loop = mock_loop

        with patch("app.session.live_adapter._omegaclaw_enqueue", return_value=("req-2", fut)), \
             patch("app.session.live_adapter._omegaclaw_available", True):
            response = _live_response_with_tool_call(
                "call-2", "agent", {"intent": "identify_person", "name": "Bob"},
            )
            await adapter._handle_server_message(response, sender)
            await asyncio.sleep(0)

        tool_events = [m for m in sender.messages if m.get("type") == "tool_event"]
        self.assertEqual(len(tool_events), 2)
        self.assertEqual(tool_events[0]["phase"], "started")
        self.assertEqual(tool_events[0]["tool_call_id"], "call-2")
        self.assertEqual(tool_events[1]["phase"], "result")
        self.assertIn("started that for you", tool_events[1]["result_summary"].lower())

    async def test_google_protected_action_prompts_for_identity_confirmation(self) -> None:
        google_state_store.set_active_user(
            LinkedGoogleUser(
                display_name="Rishi Golla",
                email="rishi@example.com",
                google_subject="google-subject-1",
                granted_scopes=["https://www.googleapis.com/auth/gmail.send"],
                connected_at="2026-04-25T21:30:00Z",
            )
        )
        session = _FakeGeminiSession()
        sender = _FakeSender()
        adapter = _build_adapter(session)
        await adapter.open(SessionContext(), _hello_payload(), sender)

        response = _live_response_with_tool_call(
            "call-google-confirm",
            "agent",
            {
                "intent": "gmail",
                "recipient": "sarah@example.com",
                "subject": "Hello",
                "body": "Checking in",
            },
        )
        await adapter._handle_server_message(response, sender, SessionContext())

        self.assertEqual(len(session.tool_response_calls), 1)
        output = session.tool_response_calls[0][0].response["output"]
        self.assertIn("are you rishi golla", output.lower())

    async def test_agent_tool_call_timeout_sends_fallback_function_response(self) -> None:
        session = _FakeGeminiSession()
        sender = _FakeSender()
        adapter = _build_adapter(session)
        await adapter.open(SessionContext(), _hello_payload(), sender)

        # Future that never resolves — background wait_for can time out; user still gets immediate copy.
        fut: asyncio.Future[dict] = asyncio.get_running_loop().create_future()

        mock_loop = AsyncMock()
        mock_loop.run_once = AsyncMock(return_value=True)
        adapter._agent_loop = mock_loop

        with patch("app.session.live_adapter._omegaclaw_enqueue", return_value=("req-3", fut)), \
             patch("app.session.live_adapter._omegaclaw_available", True), \
             patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            response = _live_response_with_tool_call("call-3", "agent", {"intent": "who is this"})
            await adapter._handle_server_message(response, sender)

        self.assertEqual(len(session.tool_response_calls), 1)
        output = session.tool_response_calls[0][0].response["output"]
        self.assertIn("started that for you", output.lower())

    async def test_agent_tool_call_omegaclaw_unavailable_sends_fallback_function_response(self) -> None:
        session = _FakeGeminiSession()
        sender = _FakeSender()
        adapter = _build_adapter(session)
        await adapter.open(SessionContext(), _hello_payload(), sender)

        with patch("app.session.live_adapter._omegaclaw_available", False):
            adapter._agent_loop = None
            response = _live_response_with_tool_call("call-4", "agent", {"intent": "who is this"})
            await adapter._handle_server_message(response, sender)

        self.assertEqual(len(session.tool_response_calls), 1)
        output = session.tool_response_calls[0][0].response["output"]
        self.assertIn("not available", output.lower())

    async def test_unknown_function_call_sends_error_function_response(self) -> None:
        session = _FakeGeminiSession()
        sender = _FakeSender()
        adapter = _build_adapter(session)
        await adapter.open(SessionContext(), _hello_payload(), sender)

        response = _live_response_with_tool_call("call-5", "unsupported_tool", {"foo": "bar"})
        await adapter._handle_server_message(response, sender)

        self.assertEqual(len(session.tool_response_calls), 1)
        fn_resp = session.tool_response_calls[0][0]
        self.assertEqual(fn_resp.name, "unsupported_tool")
        self.assertIn("Unknown function", fn_resp.response["output"])

    async def test_server_messages_are_emitted_through_sender_contract(self) -> None:
        session = _FakeGeminiSession(
            responses=[
                _live_response(session_resumption_update=_resumption_update("resume-123")),
                _live_response(
                    server_content=_server_content(
                        input_transcription=_transcription("heard this", finished=True),
                        output_transcription=_transcription("said this"),
                        model_turn=_model_turn(
                            _audio_part(b"\x00\x01", "audio/pcm;rate=16000")
                        ),
                        interrupted=True,
                        turn_complete=True,
                    )
                ),
            ]
        )
        sender = _FakeSender()
        adapter = _build_adapter(session)

        await adapter.open(SessionContext(), _hello_payload(), sender)
        await _drain_background_tasks()

        self.assertEqual(
            sender.events,
            [
                ("session_update", {"session_resume_token": "resume-123"}),
                ("transcript_in", {"text": "heard this", "is_final": True}),
                ("transcript_out", {"text": "said this", "is_final": False}),
                ("audio_chunk", {"pcm_b64": "AAE=", "sample_rate": 16000}),
                ("model_interrupt", {}),
            ],
        )
        self.assertEqual(sender.completed_turns, 1)


def _build_adapter(
    session: _FakeGeminiSession,
    *,
    client: _FakeGenaiClient | None = None,
    response_modalities: tuple[str, ...] = ("TEXT",),
    google_search_grounding: bool | None = None,
) -> GeminiLiveAdapter:
    kwargs: dict[str, Any] = {
        "live_backend": LiveBackend.GEMINI,
        "gemini_api_key": "test-key",
        "gemini_response_modalities": response_modalities,
    }
    if google_search_grounding is not None:
        kwargs["gemini_live_google_search_enabled"] = google_search_grounding
    return GeminiLiveAdapter(
        SessionSettings(**kwargs),
        client_factory=lambda **_: client or _FakeGenaiClient(session),
    )


def _hello_payload() -> dict[str, object]:
    return {
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


class _FakeSender:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []
        self.events: list[tuple[str, dict[str, object]]] = []
        self.completed_turns = 0

    async def send(self, payload: dict[str, object]) -> None:
        self.messages.append(payload)

    async def emit(self, event_type: str, payload: dict[str, object] | None = None) -> None:
        self.events.append((event_type, payload or {}))

    async def complete_output_turn(self) -> None:
        self.completed_turns += 1

    async def flush_pending(self) -> None:
        return None

    async def send_look_request(
        self,
        *,
        tool_call_id: str,
        reason: str,
        timeout_ms: int | None = None,
    ):
        return SimpleNamespace(tool_call_id=tool_call_id, reason=reason, timeout_ms=timeout_ms)

    async def send_session_update(
        self,
        *,
        session_resume_token: str,
        turn_state=None,
        resumable: bool | None = None,
    ) -> None:
        await self.emit("session_update", {"session_resume_token": session_resume_token})

    def record_server_event(self, *args, **kwargs):
        return None

    def fail_look_request(self, tool_call_id: str, reason: str):
        return SimpleNamespace(tool_call_id=tool_call_id, failure_reason=reason)

    def cancel_look_request(self, tool_call_id: str, reason: str = "look request cancelled"):
        return SimpleNamespace(tool_call_id=tool_call_id, failure_reason=reason)


class _FakeGeminiSession:
    def __init__(self, *, responses: list[object] | None = None) -> None:
        self.client_content_calls: list[tuple[dict[str, Any], bool]] = []
        self.realtime_input_calls: list[dict[str, Any]] = []
        self.tool_response_calls: list[list[Any]] = []
        self._responses = list(responses or [])

    async def send_client_content(self, *, turns, turn_complete: bool = True) -> None:
        self.client_content_calls.append((turns, turn_complete))

    async def send_realtime_input(self, **kwargs) -> None:
        self.realtime_input_calls.append(kwargs)

    async def send_tool_response(self, *, function_responses: list[Any]) -> None:
        self.tool_response_calls.append(function_responses)

    async def receive(self):
        if not self._responses:
            await asyncio.Event().wait()

        while self._responses:
            yield self._responses.pop(0)


class _FakeLiveSessionManager:
    def __init__(self, session: _FakeGeminiSession) -> None:
        self._session = session
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> _FakeGeminiSession:
        self.entered = True
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exited = True


class _FakeLiveAPI:
    def __init__(self, session: _FakeGeminiSession) -> None:
        self._manager = _FakeLiveSessionManager(session)
        self.connected_configs: list[Any] = []

    def connect(self, *, model, config):
        self.connected_configs.append(config)
        return self._manager


class _FakeAioClient:
    def __init__(self, session: _FakeGeminiSession) -> None:
        self.live = _FakeLiveAPI(session)


class _FakeGenaiClient:
    def __init__(self, session: _FakeGeminiSession) -> None:
        self.aio = _FakeAioClient(session)


async def _drain_background_tasks() -> None:
    await asyncio.sleep(0)
    await asyncio.sleep(0)


def _live_response(*, session_resumption_update=None, server_content=None) -> SimpleNamespace:
    text = None
    if (
        server_content is not None
        and getattr(server_content, "model_turn", None) is not None
        and getattr(server_content.model_turn, "parts", None)
    ):
        text_parts = [
            str(part.text)
            for part in server_content.model_turn.parts
            if getattr(part, "text", None) is not None
        ]
        if text_parts:
            text = "".join(text_parts)
    return SimpleNamespace(
        session_resumption_update=session_resumption_update,
        server_content=server_content,
        text=text,
    )


def _resumption_update(handle: str) -> SimpleNamespace:
    return SimpleNamespace(resumable=True, new_handle=handle)


def _transcription(text: str, *, finished: bool = False) -> SimpleNamespace:
    return SimpleNamespace(text=text, finished=finished)


def _server_content(
    *,
    input_transcription=None,
    output_transcription=None,
    model_turn=None,
    interrupted: bool = False,
    turn_complete: bool = False,
    generation_complete: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        input_transcription=input_transcription,
        output_transcription=output_transcription,
        model_turn=model_turn,
        interrupted=interrupted,
        turn_complete=turn_complete,
        generation_complete=generation_complete,
    )


def _model_turn(*parts) -> SimpleNamespace:
    return SimpleNamespace(parts=list(parts))


def _audio_part(data: bytes, mime_type: str) -> SimpleNamespace:
    return SimpleNamespace(text=None, inline_data=SimpleNamespace(data=data, mime_type=mime_type))


def _live_response_with_tool_call(call_id: str, name: str, args: dict[str, Any]) -> SimpleNamespace:
    fc = SimpleNamespace(id=call_id, name=name, args=args)
    return SimpleNamespace(
        session_resumption_update=None,
        server_content=None,
        tool_call=SimpleNamespace(function_calls=[fc]),
        text=None,
    )


if __name__ == "__main__":
    unittest.main()
