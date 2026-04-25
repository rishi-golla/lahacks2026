"""Live backend adapter implementations for websocket sessions."""

from __future__ import annotations

import asyncio
import base64
import binascii
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, suppress
from dataclasses import dataclass
import logging
import re
from typing import Any

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover - exercised in tests via the fallback path
    genai = None
    genai_types = None

from .coordinator import LiveAdapter, SessionContext, SessionSender
from .settings import LiveBackend, SessionSettings, get_session_settings

log = logging.getLogger(__name__)


@dataclass(slots=True)
class _FallbackHttpOptions:
    api_version: str


@dataclass(slots=True)
class _FallbackLiveConnectConfig:
    response_modalities: list[str]
    session_resumption: Any | None = None
    input_audio_transcription: Any | None = None
    output_audio_transcription: Any | None = None


@dataclass(slots=True)
class _FallbackBlob:
    data: bytes
    mime_type: str


@dataclass(slots=True)
class _FallbackSessionResumptionConfig:
    handle: str | None = None


@dataclass(slots=True)
class _FallbackAudioTranscriptionConfig:
    pass


class EchoLiveAdapter:
    """Local development adapter that mirrors client traffic back to the socket."""

    model_name = "echo"

    async def open(
        self,
        session: SessionContext,
        hello: dict[str, Any],
        sender: SessionSender,
    ) -> None:
        log.info(
            "echo live adapter open session_id=%s client=%s",
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
            "echo live adapter message session_id=%s type=%s",
            session.session_id,
            message.get("type", "?"),
        )
        await sender.send({"type": "echo", "received": message})

    async def close(self, session: SessionContext) -> None:
        log.info("echo live adapter close session_id=%s", session.session_id)


class GeminiLiveAdapter:
    """Gemini Live adapter that forwards client inputs to a Gemini Live session."""

    def __init__(
        self,
        settings: SessionSettings,
        *,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._settings = settings
        self.model_name = settings.gemini_live_model
        if client_factory is None:
            if genai is None:
                raise RuntimeError(
                    "google-genai is required to use GeminiLiveAdapter; install backend dependencies first"
                )
            client_factory = genai.Client
        self._client = client_factory(
            api_key=settings.gemini_api_key,
            http_options=self._http_options(api_version=settings.gemini_api_version),
        )
        self._live_session: Any | None = None
        self._live_session_manager: AbstractAsyncContextManager[Any] | None = None
        self._sender: SessionSender | None = None
        self._receive_task: asyncio.Task[None] | None = None
        self._closing = False

    async def open(
        self,
        session: SessionContext,
        hello: dict[str, Any],
        sender: SessionSender,
    ) -> None:
        log.info(
            "gemini live adapter connect session_id=%s client=%s model=%s",
            session.session_id,
            hello.get("client", "unknown"),
            self.model_name,
        )
        self._closing = False
        self._sender = sender
        self._live_session_manager = self._client.aio.live.connect(
            model=self.model_name,
            config=self._build_connect_config(hello),
        )
        self._live_session = await self._live_session_manager.__aenter__()
        if hasattr(self._live_session, "receive"):
            self._receive_task = asyncio.create_task(self._pump_server_events(session))

    async def handle_client_message(
        self,
        session: SessionContext,
        message: dict[str, Any],
        sender: SessionSender,
    ) -> None:
        message_type = str(message.get("type", "?"))
        log.info(
            "gemini live adapter message session_id=%s type=%s",
            session.session_id,
            message_type,
        )
        if self._live_session is None:
            await sender.send(
                {
                    "type": "error",
                    "code": "live_session_unavailable",
                    "message": "Gemini Live session is not connected",
                    "fatal": False,
                }
            )
            return

        if message_type == "text":
            await self._forward_text(message["text"])
            return
        if message_type == "audio":
            await self._forward_audio(message["pcm_b64"], sample_rate=message["sample_rate"])
            return
        if message_type == "audio_end":
            await self._live_session.send_realtime_input(audio_stream_end=True)
            return
        if message_type == "photo":
            await self._forward_photo(
                message["jpeg_b64"],
                trigger=message.get("trigger"),
                tool_call_id=message.get("tool_call_id"),
            )
            return
        if message_type == "barge_in":
            log.info("gemini live adapter barge-in session_id=%s", session.session_id)
            return

        await sender.send(
            {
                "type": "warning",
                "code": "gemini_live_unsupported",
                "message": f"Gemini Live adapter does not forward client message type {message_type} yet",
            }
        )

    async def close(self, session: SessionContext) -> None:
        self._closing = True
        if self._receive_task is not None:
            self._receive_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._receive_task
            self._receive_task = None

        if self._live_session_manager is None:
            return

        log.info("gemini live adapter close session_id=%s", session.session_id)
        await self._live_session_manager.__aexit__(None, None, None)
        self._live_session = None
        self._live_session_manager = None
        self._sender = None

    def _build_connect_config(self, hello: dict[str, Any]) -> Any:
        response_modalities = tuple(
            modality.upper() for modality in self._settings.gemini_response_modalities
        )
        wants_audio_output = "AUDIO" in response_modalities
        return self._live_connect_config(
            response_modalities=list(response_modalities),
            session_resumption=self._session_resumption_config(handle=hello.get("session_resume")),
            input_audio_transcription=(
                self._audio_transcription_config() if wants_audio_output else None
            ),
            output_audio_transcription=(
                self._audio_transcription_config() if wants_audio_output else None
            ),
        )

    async def _forward_text(self, text: str) -> None:
        await self._live_session.send_realtime_input(text=text)

    async def _forward_audio(self, pcm_b64: str, *, sample_rate: int) -> None:
        audio_bytes = self._decode_base64(pcm_b64, field_name="pcm_b64")
        await self._live_session.send_realtime_input(
            audio=self._blob(data=audio_bytes, mime_type=f"audio/pcm;rate={sample_rate}")
        )

    async def _forward_photo(
        self,
        jpeg_b64: str,
        *,
        trigger: str | None = None,
        tool_call_id: str | None = None,
    ) -> None:
        jpeg_bytes = self._decode_base64(jpeg_b64, field_name="jpeg_b64")
        log.info(
            "gemini live adapter forwarding photo bytes=%s trigger=%s tool_call_id=%s",
            len(jpeg_bytes),
            trigger,
            tool_call_id,
        )
        await self._live_session.send_realtime_input(
            video=self._blob(data=jpeg_bytes, mime_type="image/jpeg")
        )

    async def _pump_server_events(self, session: SessionContext) -> None:
        sender = self._sender
        live_session = self._live_session
        if sender is None or live_session is None:
            return

        try:
            while not self._closing:
                saw_response = False
                async for response in live_session.receive():
                    saw_response = True
                    await self._handle_server_message(response, sender)

                if self._closing:
                    break
                if not saw_response:
                    log.info(
                        "gemini live adapter receive ended without messages session_id=%s",
                        session.session_id,
                    )
                    break
                log.info(
                    "gemini live adapter turn receive complete session_id=%s",
                    session.session_id,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("gemini live adapter receive failed session_id=%s: %s", session.session_id, exc)
            if not self._closing:
                await sender.emit("session_end", {"reason": "gemini_receive_error"})
        finally:
            self._receive_task = None

    async def _handle_server_message(self, response: Any, sender: SessionSender) -> None:
        resumption_update = getattr(response, "session_resumption_update", None)
        if (
            resumption_update is not None
            and getattr(resumption_update, "resumable", False)
            and getattr(resumption_update, "new_handle", None)
        ):
            await sender.emit(
                "session_update",
                {"session_resume_token": str(resumption_update.new_handle)},
            )

        server_content = getattr(response, "server_content", None)
        if server_content is None:
            return
        log.info(
            "gemini live adapter server_content turn_complete=%s interrupted=%s",
            bool(getattr(server_content, "turn_complete", False)),
            bool(getattr(server_content, "interrupted", False)),
        )

        input_transcription = getattr(server_content, "input_transcription", None)
        if input_transcription is not None and getattr(input_transcription, "text", None):
            await sender.emit(
                "transcript_in",
                {
                    "text": str(input_transcription.text),
                    "is_final": bool(getattr(input_transcription, "finished", False)),
                },
            )

        emitted_output_transcript = False
        output_transcription = getattr(server_content, "output_transcription", None)
        if output_transcription is not None and getattr(output_transcription, "text", None):
            emitted_output_transcript = True
            await sender.emit(
                "transcript_out",
                {
                    "text": str(output_transcription.text),
                    "is_final": bool(getattr(output_transcription, "finished", False)),
                },
            )

        response_text = getattr(response, "text", None)
        if response_text and not emitted_output_transcript:
            await sender.emit(
                "transcript_out",
                {
                    "text": str(response_text),
                    "is_final": bool(
                        getattr(server_content, "generation_complete", False)
                        or getattr(server_content, "turn_complete", False)
                    ),
                },
            )

        model_turn = getattr(server_content, "model_turn", None)
        parts = getattr(model_turn, "parts", None) or []
        if parts:
            log.info("gemini live adapter model_turn parts=%s", len(parts))
        for part in parts:
            inline_data = getattr(part, "inline_data", None)
            if inline_data is None or getattr(inline_data, "data", None) is None:
                continue
            mime_type = str(getattr(inline_data, "mime_type", "") or "")
            if not mime_type.startswith("audio/pcm"):
                continue

            log.info(
                "gemini live adapter audio chunk bytes=%s mime_type=%s",
                len(inline_data.data),
                mime_type,
            )
            await sender.emit(
                "audio_chunk",
                {
                    "pcm_b64": base64.b64encode(inline_data.data).decode("ascii"),
                    "sample_rate": _sample_rate_from_mime_type(mime_type),
                },
            )

        if getattr(server_content, "interrupted", False):
            await sender.emit("model_interrupt", {})

        if getattr(server_content, "turn_complete", False):
            await sender.complete_output_turn()

    @staticmethod
    def _decode_base64(value: str, *, field_name: str) -> bytes:
        try:
            return base64.b64decode(value, validate=True)
        except binascii.Error as exc:
            raise ValueError(f"{field_name} must be valid base64 data") from exc

    @staticmethod
    def _blob(*, data: bytes, mime_type: str) -> Any:
        if genai_types is not None:
            return genai_types.Blob(data=data, mime_type=mime_type)
        return _FallbackBlob(data=data, mime_type=mime_type)

    @staticmethod
    def _http_options(*, api_version: str) -> Any:
        if genai_types is not None:
            return genai_types.HttpOptions(api_version=api_version)
        return _FallbackHttpOptions(api_version=api_version)

    @staticmethod
    def _live_connect_config(
        *,
        response_modalities: list[str],
        session_resumption: Any | None = None,
        input_audio_transcription: Any | None = None,
        output_audio_transcription: Any | None = None,
    ) -> Any:
        if genai_types is not None:
            return genai_types.LiveConnectConfig(
                response_modalities=response_modalities,
                session_resumption=session_resumption,
                input_audio_transcription=input_audio_transcription,
                output_audio_transcription=output_audio_transcription,
            )
        return _FallbackLiveConnectConfig(
            response_modalities=response_modalities,
            session_resumption=session_resumption,
            input_audio_transcription=input_audio_transcription,
            output_audio_transcription=output_audio_transcription,
        )

    @staticmethod
    def _session_resumption_config(*, handle: str | None) -> Any:
        if genai_types is not None:
            return genai_types.SessionResumptionConfig(handle=handle)
        return _FallbackSessionResumptionConfig(handle=handle)

    @staticmethod
    def _audio_transcription_config() -> Any:
        if genai_types is not None:
            return genai_types.AudioTranscriptionConfig()
        return _FallbackAudioTranscriptionConfig()


_PCM_RATE_RE = re.compile(r"(?:^|[;,\s])rate=(\d+)(?:$|[;,\s])")


def _sample_rate_from_mime_type(mime_type: str) -> int:
    match = _PCM_RATE_RE.search(mime_type)
    if match is None:
        return 24_000
    return int(match.group(1))


def build_live_adapter(settings: SessionSettings | None = None) -> LiveAdapter:
    """Build the configured live adapter from environment-backed settings."""

    resolved_settings = settings or get_session_settings()
    if resolved_settings.live_backend is LiveBackend.GEMINI:
        return GeminiLiveAdapter(resolved_settings)
    return EchoLiveAdapter()
