"""Live backend adapter implementations for websocket sessions."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
import logging
from typing import Any

from google import genai
from google.genai import types as genai_types

from .coordinator import LiveAdapter, SessionContext, SessionSender
from .settings import LiveBackend, SessionSettings, get_session_settings

log = logging.getLogger(__name__)


class EchoLiveAdapter:
    """Local development adapter that mirrors client traffic back to the socket."""

    model_name = "echo"

    async def open(self, session: SessionContext, hello: dict[str, Any]) -> None:
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
    """Gemini Live adapter with connection management in place for later event wiring."""

    def __init__(
        self,
        settings: SessionSettings,
        *,
        client_factory: Callable[..., genai.Client] = genai.Client,
    ) -> None:
        self._settings = settings
        self.model_name = settings.gemini_live_model
        self._client = client_factory(
            api_key=settings.gemini_api_key,
            http_options=genai_types.HttpOptions(api_version=settings.gemini_api_version),
        )
        self._live_session: Any | None = None
        self._live_session_manager: AbstractAsyncContextManager[Any] | None = None

    async def open(self, session: SessionContext, hello: dict[str, Any]) -> None:
        log.info(
            "gemini live adapter connect session_id=%s client=%s model=%s",
            session.session_id,
            hello.get("client", "unknown"),
            self.model_name,
        )
        self._live_session_manager = self._client.aio.live.connect(
            model=self.model_name,
            config=self._build_connect_config(),
        )
        self._live_session = await self._live_session_manager.__aenter__()

    async def handle_client_message(
        self,
        session: SessionContext,
        message: dict[str, Any],
        sender: SessionSender,
    ) -> None:
        log.info(
            "gemini live adapter stub session_id=%s type=%s",
            session.session_id,
            message.get("type", "?"),
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

        # Full Gemini event mapping lands in a later issue. For now we keep the
        # connection lifecycle real while deferring multimodal message plumbing.
        await sender.send(
            {
                "type": "warning",
                "code": "gemini_live_stub",
                "message": f"Gemini Live adapter received {message.get('type', '?')} but forwarding is not wired yet",
            }
        )

    async def close(self, session: SessionContext) -> None:
        if self._live_session_manager is None:
            return

        log.info("gemini live adapter close session_id=%s", session.session_id)
        await self._live_session_manager.__aexit__(None, None, None)
        self._live_session = None
        self._live_session_manager = None

    def _build_connect_config(self) -> genai_types.LiveConnectConfig:
        return genai_types.LiveConnectConfig(
            response_modalities=list(self._settings.gemini_response_modalities),
        )


def build_live_adapter(settings: SessionSettings | None = None) -> LiveAdapter:
    """Build the configured live adapter from environment-backed settings."""

    resolved_settings = settings or get_session_settings()
    if resolved_settings.live_backend is LiveBackend.GEMINI:
        return GeminiLiveAdapter(resolved_settings)
    return EchoLiveAdapter()
