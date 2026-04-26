from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import omegaclaw.remote.uagents_bridge as bridge  # noqa: E402


REAL_AGENT_ADDRESS = "agent1qdy95pwgw3uvp2vgv8qjpdaykhtpmfcegpwqdk5leh2lg36tpq3c66zggm0"


class UAgentsBridgeTests(unittest.TestCase):
    # ------------------------------------------------------------------
    # Module-level constants
    # ------------------------------------------------------------------

    def test_default_agent_address_matches_deployed_contextlens(self) -> None:
        self.assertEqual(bridge.CONTEXTLENS_AGENT_ADDRESS, REAL_AGENT_ADDRESS)

    # ------------------------------------------------------------------
    # Unavailable path (uagents not installed — the normal test env)
    # ------------------------------------------------------------------

    def test_raises_runtime_error_when_uagents_unavailable(self) -> None:
        async def _run() -> None:
            with patch.object(bridge, "_uagents_available", False):
                with self.assertRaises(RuntimeError, msg="uagents package not installed"):
                    await bridge.query_identify_person("Alice", "Fetch.ai", "CEO")

        asyncio.run(_run())

    def test_runtime_error_message_mentions_uagents(self) -> None:
        async def _run() -> None:
            with patch.object(bridge, "_uagents_available", False):
                try:
                    await bridge.query_identify_person("Bob", "Acme", "")
                except RuntimeError as exc:
                    self.assertIn("uagents", str(exc).lower())

        asyncio.run(_run())

    # ------------------------------------------------------------------
    # Timeout path (uagents installed but agent returns None)
    # ------------------------------------------------------------------

    def test_raises_timeout_error_when_response_is_none(self) -> None:
        async def _run() -> None:
            mock_query = AsyncMock(return_value=None)
            mock_query_cls = MagicMock(return_value=MagicMock())

            with patch.object(bridge, "_uagents_available", True), patch(
                "omegaclaw.remote.uagents_bridge._uagents_query", mock_query, create=True
            ), patch("omegaclaw.remote.uagents_bridge._PersonQuery", mock_query_cls, create=True):
                with self.assertRaises(TimeoutError):
                    await bridge.query_identify_person("Alice", "Fetch.ai", "CEO", timeout=5.0)

        asyncio.run(_run())

    def test_timeout_error_message_includes_agent_address(self) -> None:
        async def _run() -> None:
            mock_query = AsyncMock(return_value=None)
            mock_query_cls = MagicMock(return_value=MagicMock())

            with patch.object(bridge, "_uagents_available", True), patch(
                "omegaclaw.remote.uagents_bridge._uagents_query", mock_query, create=True
            ), patch("omegaclaw.remote.uagents_bridge._PersonQuery", mock_query_cls, create=True):
                try:
                    await bridge.query_identify_person("Alice", "Fetch.ai", "CEO", agent_address="agent1qtest")
                except TimeoutError as exc:
                    self.assertIn("agent1qtest", str(exc))

        asyncio.run(_run())

    # ------------------------------------------------------------------
    # Success path
    # ------------------------------------------------------------------

    def test_successful_query_returns_summary_confidence_source(self) -> None:
        async def _run() -> dict:
            payload_json = '{"summary": "Alice is a senior engineer.", "confidence": "high", "source": "gemini"}'

            mock_response = MagicMock()
            mock_response.decode_payload.return_value = payload_json

            mock_ctx = MagicMock()
            mock_ctx.summary = "Alice is a senior engineer."
            mock_ctx.confidence = "high"
            mock_ctx.source = "gemini"

            mock_context_cls = MagicMock()
            mock_context_cls.model_validate_json.return_value = mock_ctx

            mock_query = AsyncMock(return_value=mock_response)
            mock_query_cls = MagicMock(return_value=MagicMock())

            with patch.object(bridge, "_uagents_available", True), patch(
                "omegaclaw.remote.uagents_bridge._uagents_query", mock_query, create=True
            ), patch(
                "omegaclaw.remote.uagents_bridge._PersonQuery", mock_query_cls, create=True
            ), patch(
                "omegaclaw.remote.uagents_bridge._PersonContext", mock_context_cls, create=True
            ):
                return await bridge.query_identify_person("Alice", "Fetch.ai", "Senior Engineer")

        result = asyncio.run(_run())
        self.assertEqual(result["summary"], "Alice is a senior engineer.")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["source"], "gemini")

    def test_successful_query_passes_correct_args_to_uagents_query(self) -> None:
        async def _run() -> None:
            mock_response = MagicMock()
            mock_response.decode_payload.return_value = '{"summary": "x", "confidence": "low", "source": "gemini"}'

            mock_ctx = MagicMock(summary="x", confidence="low", source="gemini")
            mock_context_cls = MagicMock()
            mock_context_cls.model_validate_json.return_value = mock_ctx

            fake_message = MagicMock()
            mock_query_cls = MagicMock(return_value=fake_message)
            mock_query = AsyncMock(return_value=mock_response)

            with patch.object(bridge, "_uagents_available", True), patch(
                "omegaclaw.remote.uagents_bridge._uagents_query", mock_query, create=True
            ), patch(
                "omegaclaw.remote.uagents_bridge._PersonQuery", mock_query_cls, create=True
            ), patch(
                "omegaclaw.remote.uagents_bridge._PersonContext", mock_context_cls, create=True
            ):
                await bridge.query_identify_person(
                    "Bob", "OpenAI", "Researcher", timeout=12.0, agent_address="agent1qcustom"
                )

            mock_query.assert_awaited_once()
            call_kwargs = mock_query.await_args.kwargs
            self.assertEqual(call_kwargs["destination"], "agent1qcustom")
            self.assertEqual(call_kwargs["timeout"], 12.0)
            self.assertEqual(call_kwargs["message"], fake_message)

            mock_query_cls.assert_called_once_with(name="Bob", organization="OpenAI", title="Researcher")

    def test_decode_payload_result_fed_to_model_validate_json(self) -> None:
        async def _run() -> None:
            payload_json = '{"summary": "z", "confidence": "high", "source": "test"}'

            mock_response = MagicMock()
            mock_response.decode_payload.return_value = payload_json

            mock_ctx = MagicMock(summary="z", confidence="high", source="test")
            mock_context_cls = MagicMock()
            mock_context_cls.model_validate_json.return_value = mock_ctx

            mock_query = AsyncMock(return_value=mock_response)
            mock_query_cls = MagicMock(return_value=MagicMock())

            with patch.object(bridge, "_uagents_available", True), patch(
                "omegaclaw.remote.uagents_bridge._uagents_query", mock_query, create=True
            ), patch(
                "omegaclaw.remote.uagents_bridge._PersonQuery", mock_query_cls, create=True
            ), patch(
                "omegaclaw.remote.uagents_bridge._PersonContext", mock_context_cls, create=True
            ):
                await bridge.query_identify_person("Z", "Corp", "")

            mock_context_cls.model_validate_json.assert_called_once_with(payload_json)

    # ------------------------------------------------------------------
    # Default address used when none supplied
    # ------------------------------------------------------------------

    def test_default_address_forwarded_to_uagents_query(self) -> None:
        async def _run() -> None:
            mock_response = MagicMock()
            mock_response.decode_payload.return_value = '{"summary": "ok", "confidence": "high", "source": "gemini"}'

            mock_ctx = MagicMock(summary="ok", confidence="high", source="gemini")
            mock_context_cls = MagicMock()
            mock_context_cls.model_validate_json.return_value = mock_ctx

            mock_query = AsyncMock(return_value=mock_response)
            mock_query_cls = MagicMock(return_value=MagicMock())

            with patch.object(bridge, "_uagents_available", True), patch(
                "omegaclaw.remote.uagents_bridge._uagents_query", mock_query, create=True
            ), patch(
                "omegaclaw.remote.uagents_bridge._PersonQuery", mock_query_cls, create=True
            ), patch(
                "omegaclaw.remote.uagents_bridge._PersonContext", mock_context_cls, create=True
            ):
                await bridge.query_identify_person("Eve", "Anthropic", "Engineer")

            call_kwargs = mock_query.await_args.kwargs
            self.assertEqual(call_kwargs["destination"], REAL_AGENT_ADDRESS)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
