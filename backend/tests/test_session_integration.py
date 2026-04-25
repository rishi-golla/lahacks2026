from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

if "google.genai" not in sys.modules:
    google_module = sys.modules.setdefault("google", ModuleType("google"))
    genai_module = ModuleType("google.genai")

    class _StubHttpOptions:
        def __init__(self, *, api_version: str) -> None:
            self.api_version = api_version

    class _StubLiveConnectConfig:
        def __init__(
            self,
            *,
            response_modalities,
            session_resumption=None,
            input_audio_transcription=None,
            output_audio_transcription=None,
        ) -> None:
            self.response_modalities = response_modalities
            self.session_resumption = session_resumption
            self.input_audio_transcription = input_audio_transcription
            self.output_audio_transcription = output_audio_transcription

    class _StubSessionResumptionConfig:
        def __init__(self, *, handle=None) -> None:
            self.handle = handle

    class _StubAudioTranscriptionConfig:
        pass

    class _StubClient:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

    genai_module.Client = _StubClient
    genai_module.types = SimpleNamespace(
        HttpOptions=_StubHttpOptions,
        LiveConnectConfig=_StubLiveConnectConfig,
        SessionResumptionConfig=_StubSessionResumptionConfig,
        AudioTranscriptionConfig=_StubAudioTranscriptionConfig,
    )
    google_module.genai = genai_module
    sys.modules["google.genai"] = genai_module

from app.main import app
from app.session.coordinator import SessionCoordinator
from app.session.live_adapter import GeminiLiveAdapter
from app.session.settings import LiveBackend, SessionSettings


class GeminiSessionIntegrationTests(unittest.TestCase):
    def test_hello_opens_gemini_live_session_and_ready_exposes_model(self) -> None:
        recorder = _GeminiLiveRecorder()
        adapter = _build_gemini_adapter(recorder)

        with _session_socket(adapter) as websocket:
            websocket.send_json(_hello_payload(session_resume="resume-from-client"))

            ready = websocket.receive_json()

        self.assertEqual(
            ready,
            {
                "type": "ready",
                "session_id": ready["session_id"],
                "session_resume_token": ready["session_resume_token"],
                "resumed": True,
                "model": "gemini-live-test-model",
            },
        )
        self.assertTrue(ready["session_id"].startswith("session-"))
        self.assertTrue(ready["session_resume_token"].startswith("resume-"))
        self.assertEqual(len(recorder.connect_calls), 1)
        connect_call = recorder.connect_calls[0]
        self.assertEqual(connect_call["model"], "gemini-live-test-model")
        self.assertEqual(list(connect_call["config"].response_modalities), ["TEXT"])
        self.assertEqual(connect_call["config"].session_resumption.handle, "resume-from-client")
        self.assertEqual(recorder.entered_sessions, [recorder.live_session])
        self.assertEqual(recorder.exited_sessions, [recorder.live_session])

    def test_post_handshake_text_is_forwarded_into_gemini_live_session(self) -> None:
        recorder = _GeminiLiveRecorder()
        adapter = _build_gemini_adapter(recorder)

        with _session_socket(adapter) as websocket:
            websocket.send_json(_hello_payload())
            self.assertEqual(websocket.receive_json()["type"], "ready")

            websocket.send_json({"type": "text", "text": "hello Gemini"})
        self.assertEqual(
            recorder.live_session.client_content_calls,
            [
                (
                    {
                        "role": "user",
                        "parts": [{"text": "hello Gemini"}],
                    },
                    True,
                )
            ],
        )

    def test_client_disconnect_closes_gemini_live_context_manager(self) -> None:
        recorder = _GeminiLiveRecorder()
        adapter = _build_gemini_adapter(recorder)

        socket = _session_socket(adapter)
        with socket as websocket:
            websocket.send_json(_hello_payload())
            self.assertEqual(websocket.receive_json()["type"], "ready")

        self.assertEqual(recorder.enter_count, 1)
        self.assertEqual(recorder.exit_count, 1)
        self.assertIsNone(adapter._live_session)
        self.assertIsNone(adapter._live_session_manager)

    def test_open_failure_returns_internal_error_and_still_cleans_up_live_manager(self) -> None:
        recorder = _GeminiLiveRecorder(enter_error=RuntimeError("boom"))
        adapter = _build_gemini_adapter(recorder)

        with _session_socket(adapter) as websocket:
            websocket.send_json(_hello_payload())

            error = websocket.receive_json()

            with self.assertRaises(Exception):
                websocket.receive_json()

        self.assertEqual(
            error,
            {
                "type": "error",
                "code": "internal_error",
                "message": "internal session error",
                "fatal": True,
            },
        )
        self.assertEqual(recorder.enter_count, 1)
        self.assertEqual(recorder.exit_count, 1)
        self.assertEqual(recorder.exited_sessions, [recorder.live_session])
        self.assertIsNone(adapter._live_session)
        self.assertIsNone(adapter._live_session_manager)


def _build_gemini_adapter(recorder: "_GeminiLiveRecorder") -> GeminiLiveAdapter:
    settings = SessionSettings(
        LIVE_BACKEND=LiveBackend.GEMINI,
        GEMINI_API_KEY="test-api-key",
        GEMINI_LIVE_MODEL="gemini-live-test-model",
        GEMINI_API_VERSION="v1alpha",
        GEMINI_RESPONSE_MODALITIES=("TEXT",),
    )
    return GeminiLiveAdapter(settings, client_factory=recorder.build_client)


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


def _session_socket(adapter: GeminiLiveAdapter):
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


class _GeminiLiveRecorder:
    def __init__(self, *, enter_error: Exception | None = None) -> None:
        self.enter_error = enter_error
        self.connect_calls: list[dict[str, object]] = []
        self.entered_sessions: list[object] = []
        self.exited_sessions: list[object] = []
        self.enter_count = 0
        self.exit_count = 0
        self.live_session = _FakeGeminiSession()

    def build_client(self, **kwargs):
        self.client_kwargs = kwargs
        return _FakeGenaiClient(self)


class _FakeGenaiClient:
    def __init__(self, recorder: _GeminiLiveRecorder) -> None:
        self.aio = _FakeAioClient(recorder)


class _FakeAioClient:
    def __init__(self, recorder: _GeminiLiveRecorder) -> None:
        self.live = _FakeLiveNamespace(recorder)


class _FakeLiveNamespace:
    def __init__(self, recorder: _GeminiLiveRecorder) -> None:
        self._recorder = recorder

    def connect(self, *, model, config):
        self._recorder.connect_calls.append({"model": model, "config": config})
        return _FakeLiveSessionManager(self._recorder)


class _FakeLiveSessionManager:
    def __init__(self, recorder: _GeminiLiveRecorder) -> None:
        self._recorder = recorder

    async def __aenter__(self):
        self._recorder.enter_count += 1
        if self._recorder.enter_error is not None:
            raise self._recorder.enter_error
        self._recorder.entered_sessions.append(self._recorder.live_session)
        return self._recorder.live_session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._recorder.exit_count += 1
        self._recorder.exited_sessions.append(self._recorder.live_session)


class _FakeGeminiSession:
    def __init__(self) -> None:
        self.client_content_calls: list[tuple[dict[str, object], bool]] = []
        self.realtime_input_calls: list[dict[str, object]] = []

    async def send_client_content(self, *, turns, turn_complete: bool = True) -> None:
        self.client_content_calls.append((turns, turn_complete))

    async def send_realtime_input(self, **kwargs) -> None:
        self.realtime_input_calls.append(kwargs)

    async def receive(self):
        if False:
            yield None


if __name__ == "__main__":
    unittest.main()
