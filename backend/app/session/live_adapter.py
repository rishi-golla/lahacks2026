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
import sys
from pathlib import Path
from typing import Any

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover - exercised in tests via the fallback path
    genai = None
    genai_types = None

# Add project root to path so omegaclaw is importable from the backend
_PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from omegaclaw.channels.my_backend import enqueue_message as _omegaclaw_enqueue
    from omegaclaw.channels.backend_channel import BackendChannel as _BackendChannel
    from omegaclaw.channels.backend_channel import GlassesTask as _GlassesTask
    from omegaclaw.runtime_loop import OmegaClawAgentLoop as _OmegaClawAgentLoop
    _omegaclaw_available = True
except ImportError:  # pragma: no cover
    _omegaclaw_enqueue = None
    _BackendChannel = None
    _GlassesTask = None
    _OmegaClawAgentLoop = None
    _omegaclaw_available = False

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
    system_instruction: str | None = None
    tools: list[Any] | None = None


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


@dataclass(slots=True)
class _FallbackFunctionDeclaration:
    name: str
    description: str
    parameters: Any | None = None


@dataclass(slots=True)
class _FallbackSchema:
    type: str
    properties: dict | None = None
    required: list | None = None
    description: str | None = None


@dataclass(slots=True)
class _FallbackTool:
    function_declarations: list | None = None


@dataclass(slots=True)
class _FallbackFunctionResponse:
    id: str
    name: str
    response: dict


def _system_instruction(*, google_search_grounding: bool) -> str:
    """Session system text for Gemini Live (grounding changes search routing)."""
    base = (
        "You are a hands-free assistant for smart glasses. "
        "Treat incoming realtime image/video frames as the user's current point-of-view camera feed. "
        "Answer visual questions directly from the frame when one is present.\n\n"
    )
    if google_search_grounding:
        grounding = (
            "You have built-in Google Search for public web lookups, facts, news, and general questions. "
            "Prefer it for those — you do not need the agent tool for ordinary web search.\n\n"
            "You have an 'agent' function that routes specialist tasks to the OmegaClaw backend. Use it for:\n"
            "- To identify a person: if a badge is visible, extract name, organization, and title, "
            "then call agent(intent='identify_person', name=..., organization=..., title=...).\n"
            "- To describe the scene: call agent(intent='describe_scene', "
            "image_context='brief text description of what you see').\n"
            "Do not use agent(intent='google_search') for general web questions when built-in search "
            "can answer; reserve it only if the user explicitly needs the backend search path.\n\n"
        )
    else:
        grounding = (
            "You have an 'agent' function that routes specialist tasks to backend skills. Use it:\n"
            "- To identify a person: if a badge is visible, extract name, organization, and title, "
            "then call agent(intent='identify_person', name=..., organization=..., title=...).\n"
            "- To describe the scene: call agent(intent='describe_scene', "
            "image_context='brief text description of what you see').\n"
            "- To search the web: call agent(intent='google_search', query=...).\n\n"
        )
    ack = (
        "Before calling agent, always speak a brief acknowledgment first so the user knows you "
        "heard them and work is in progress — for example: "
        "\"Got it, looking that up,\" before a search or agent handoff; "
        "\"One sec, checking who that is,\" for identify_person; "
        "\"Let me describe what I'm seeing,\" for describe_scene. "
        "Never call agent silently; the backend may take several seconds.\n\n"
        "For general conversation or questions you can answer directly without tools, do not call agent. "
        "Keep spoken responses short and natural — the user cannot see a screen."
    )
    return base + grounding + ack


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
        self._agent_loop = _OmegaClawAgentLoop() if _omegaclaw_available else None
        self._backend_channel = _BackendChannel() if _BackendChannel is not None else None
        if not _omegaclaw_available:
            log.warning("gemini live adapter omegaclaw not available — agent tool calls will return fallback")

    async def open(
        self,
        session: SessionContext,
        hello: dict[str, Any],
        sender: SessionSender,
    ) -> None:
        log.info(
            "gemini live adapter connect session_id=%s client=%s model=%s google_search_grounding=%s",
            session.session_id,
            hello.get("client", "unknown"),
            self.model_name,
            self._google_search_grounding_active(),
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
        log_method = log.debug if message_type == "audio" else log.info
        log_method(
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

    def _google_search_grounding_active(self) -> bool:
        return bool(self._settings.gemini_live_google_search_enabled and genai_types is not None)

    def _live_tools(self) -> list[Any]:
        tools: list[Any] = []
        if self._google_search_grounding_active():
            tools.append(genai_types.Tool(google_search=genai_types.GoogleSearch()))
        tools.append(self._make_agent_tool())
        return tools

    def _build_connect_config(self, hello: dict[str, Any]) -> Any:
        response_modalities = tuple(
            modality.upper() for modality in self._settings.gemini_response_modalities
        )
        wants_audio_output = "AUDIO" in response_modalities
        if self._settings.gemini_live_google_search_enabled and genai_types is None:
            log.warning(
                "gemini live google search enabled in settings but google.genai.types is unavailable"
            )
        return self._live_connect_config(
            response_modalities=list(response_modalities),
            session_resumption=self._session_resumption_config(handle=hello.get("session_resume")),
            system_instruction=_system_instruction(
                google_search_grounding=self._google_search_grounding_active(),
            ),
            tools=self._live_tools(),
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
                    await self._handle_server_message(response, sender, session)

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

    async def _handle_server_message(self, response: Any, sender: SessionSender, session: SessionContext | None = None) -> None:
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

        # Handle model tool calls before server_content
        tool_call = getattr(response, "tool_call", None)
        if tool_call is not None:
            function_calls = getattr(tool_call, "function_calls", None) or []
            for fc in function_calls:
                await self._handle_function_call(fc, sender, session)

        server_content = getattr(response, "server_content", None)
        if server_content is None:
            return
        log.debug(
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
            log.debug("gemini live adapter model_turn parts=%s", len(parts))
        for part in parts:
            inline_data = getattr(part, "inline_data", None)
            if inline_data is None or getattr(inline_data, "data", None) is None:
                continue
            mime_type = str(getattr(inline_data, "mime_type", "") or "")
            if not mime_type.startswith("audio/pcm"):
                continue

            log.debug(
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

    async def _handle_function_call(
        self,
        fc: Any,
        sender: SessionSender,
        session: SessionContext | None = None,
    ) -> None:
        name = str(getattr(fc, "name", "") or "")
        args = dict(getattr(fc, "args", {}) or {})
        fc_id = str(getattr(fc, "id", "") or "")

        log.info("gemini live adapter function_call name=%s id=%s args=%s", name, fc_id, args)

        if name == "agent":
            await self._handle_agent_tool_call(fc_id, args, sender, session)
        else:
            log.warning("gemini live adapter unhandled function call name=%s", name)
            if self._live_session is not None:
                await self._live_session.send_tool_response(
                    function_responses=[
                        self._function_response(
                            id=fc_id,
                            name=name,
                            output=f"Unknown function: {name}",
                        )
                    ]
                )

    async def _handle_agent_tool_call(
        self,
        call_id: str,
        args: dict[str, Any],
        sender: SessionSender,
        session: SessionContext | None = None,
    ) -> None:
        intent = str(args.pop("intent", ""))
        log.info("gemini live adapter agent tool intent=%s args=%s", intent, args)

        # Notify iOS debug UI that a tool call started
        await sender.send({
            "type": "tool_event",
            "tool_call_id": call_id,
            "name": "agent",
            "phase": "started",
            "args": {k: v for k, v in {"intent": intent, **args}.items()},
        })

        summary: str
        if not _omegaclaw_available or self._agent_loop is None:
            summary = "Agent skills are not available right now."
            log.warning("gemini live adapter agent tool called but omegaclaw not available")
        elif self._backend_channel is not None and _GlassesTask is not None and session is not None:
            try:
                result = await self._backend_channel.submit(
                    _GlassesTask(
                        session_id=session.session_id,
                        turn_id=call_id,
                        intent=intent,
                        tool_call_id=call_id,
                        args=args,
                    )
                )
                summary = (
                    result.get("summary")
                    or result.get("description")
                    or str(result)
                )
            except Exception as exc:  # noqa: BLE001
                summary = "I had trouble completing that request."
                log.exception("gemini live adapter backend channel failed intent=%s: %s", intent, exc)
        else:
            try:
                request_id, fut = _omegaclaw_enqueue({
                    "intent": intent,
                    "args": args,
                })
                await self._agent_loop.run_once()
                response_payload = await asyncio.wait_for(fut, timeout=10.0)
                result = response_payload.get("result", {})
                if isinstance(result, dict):
                    summary = (
                        result.get("summary")
                        or result.get("description")
                        or str(result)
                    )
                else:
                    summary = str(result)
            except asyncio.TimeoutError:
                summary = "The request timed out. Please try again."
                log.warning("gemini live adapter agent tool timed out intent=%s", intent)
            except Exception as exc:  # noqa: BLE001
                summary = "I had trouble completing that request."
                log.exception("gemini live adapter agent tool failed intent=%s: %s", intent, exc)

        log.info("gemini live adapter agent tool result intent=%s summary=%r", intent, summary[:120])

        # Notify iOS debug UI of result
        await sender.send({
            "type": "tool_event",
            "tool_call_id": call_id,
            "name": "agent",
            "phase": "result",
            "result_summary": summary,
        })

        # Send function response back to Gemini so it can speak the result
        if self._live_session is not None:
            await self._live_session.send_tool_response(
                function_responses=[
                    self._function_response(id=call_id, name="agent", output=summary)
                ]
            )

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
    def _make_agent_tool() -> Any:
        """Build the 'agent' function declaration for Gemini Live."""
        if genai_types is not None:
            str_schema = genai_types.Schema(type=genai_types.Type.STRING)
            return genai_types.Tool(
                function_declarations=[
                    genai_types.FunctionDeclaration(
                        name="agent",
                        description=(
                            "Route a specialist task to the OmegaClaw backend. "
                            "Use for person identification, scene description, or web search."
                        ),
                        parameters=genai_types.Schema(
                            type=genai_types.Type.OBJECT,
                            properties={
                                "intent": genai_types.Schema(
                                    type=genai_types.Type.STRING,
                                    description="What the user wants, e.g. 'identify_person', 'describe_scene', 'google_search'",
                                ),
                                "name": str_schema,
                                "organization": str_schema,
                                "title": str_schema,
                                "image_context": genai_types.Schema(
                                    type=genai_types.Type.STRING,
                                    description="Brief text description of the scene for describe_scene",
                                ),
                                "query": genai_types.Schema(
                                    type=genai_types.Type.STRING,
                                    description="Search query for google_search",
                                ),
                            },
                            required=["intent"],
                        ),
                    )
                ]
            )
        # Fallback (no-op when genai_types unavailable)
        return _FallbackTool(
            function_declarations=[
                _FallbackFunctionDeclaration(
                    name="agent",
                    description="Route a specialist task to OmegaClaw.",
                )
            ]
        )

    @staticmethod
    def _function_response(*, id: str, name: str, output: str) -> Any:
        if genai_types is not None:
            return genai_types.FunctionResponse(id=id, name=name, response={"output": output})
        return _FallbackFunctionResponse(id=id, name=name, response={"output": output})

    @staticmethod
    def _live_connect_config(
        *,
        response_modalities: list[str],
        session_resumption: Any | None = None,
        input_audio_transcription: Any | None = None,
        output_audio_transcription: Any | None = None,
        system_instruction: str | None = None,
        tools: list[Any] | None = None,
    ) -> Any:
        if genai_types is not None:
            return genai_types.LiveConnectConfig(
                response_modalities=response_modalities,
                session_resumption=session_resumption,
                system_instruction=system_instruction,
                input_audio_transcription=input_audio_transcription,
                output_audio_transcription=output_audio_transcription,
                tools=tools,
            )
        return _FallbackLiveConnectConfig(
            response_modalities=response_modalities,
            session_resumption=session_resumption,
            input_audio_transcription=input_audio_transcription,
            output_audio_transcription=output_audio_transcription,
            system_instruction=system_instruction,
            tools=tools,
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
