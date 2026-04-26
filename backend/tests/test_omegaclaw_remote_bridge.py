from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from omegaclaw.remote import agentverse_bridge as bridge  # noqa: E402

REAL_AGENT_ADDRESS = "agent1qdy95pwgw3uvp2vgv8qjpdaykhtpmfcegpwqdk5leh2lg36tpq3c66zggm0"


class RemoteBridgeTests(unittest.TestCase):
    # ------------------------------------------------------------------
    # identify_person.json config
    # ------------------------------------------------------------------

    def test_identify_person_json_has_real_deployed_agent_address(self) -> None:
        cfg = bridge.load_skill_config("identify_person")
        self.assertEqual(cfg["agent_address"], REAL_AGENT_ADDRESS)

    def test_identify_person_json_has_required_fields(self) -> None:
        cfg = bridge.load_skill_config("identify_person")
        for field in ("skill_name", "agent_address", "input_schema", "output_schema"):
            self.assertIn(field, cfg, f"missing field: {field}")

    # ------------------------------------------------------------------
    # invoke_identify_person — uAgents-first path
    # ------------------------------------------------------------------

    def test_invoke_identify_person_uses_uagents_when_available(self) -> None:
        async def _run() -> dict:
            mock_uagents = AsyncMock(return_value={"summary": "via P2P", "confidence": "high", "source": "gemini"})
            with patch.object(bridge, "_uagents_identify", mock_uagents), patch.object(
                bridge, "invoke_remote_skill"
            ) as mock_http:
                result = await bridge.invoke_identify_person("Alice", "Fetch.ai", "CEO")
                mock_uagents.assert_awaited_once()
                mock_http.assert_not_awaited()
                return result

        result = asyncio.run(_run())
        self.assertEqual(result["summary"], "via P2P")
        self.assertEqual(result["source"], "agentverse:identify_person")

    def test_invoke_identify_person_passes_agent_address_from_json_config(self) -> None:
        async def _run() -> None:
            mock_uagents = AsyncMock(return_value={"summary": "ok", "confidence": "high", "source": "gemini"})
            with patch.object(bridge, "_uagents_identify", mock_uagents):
                await bridge.invoke_identify_person("Bob", "Acme", "Engineer")
            call_kwargs = mock_uagents.await_args.kwargs
            self.assertEqual(call_kwargs["agent_address"], REAL_AGENT_ADDRESS)

        asyncio.run(_run())

    def test_invoke_identify_person_passes_timeout_from_json_config(self) -> None:
        async def _run() -> None:
            mock_uagents = AsyncMock(return_value={"summary": "ok", "confidence": "high", "source": "gemini"})
            cfg_with_timeout = {"agent_address": REAL_AGENT_ADDRESS, "timeout_ms": 3000}
            with patch.object(bridge, "_uagents_identify", mock_uagents), patch.object(
                bridge, "load_skill_config", return_value=cfg_with_timeout
            ):
                await bridge.invoke_identify_person("Carol", "Corp", "")
            call_kwargs = mock_uagents.await_args.kwargs
            self.assertAlmostEqual(call_kwargs["timeout"], 3.0)

        asyncio.run(_run())

    def test_invoke_identify_person_falls_back_to_http_on_runtime_error(self) -> None:
        async def _run() -> dict:
            mock_uagents = AsyncMock(side_effect=RuntimeError("uagents package not installed"))
            with patch.object(bridge, "_uagents_identify", mock_uagents), patch.object(
                bridge, "invoke_remote_skill", return_value={"summary": "http fallback", "confidence": "low"}
            ) as mock_http:
                result = await bridge.invoke_identify_person("Dave", "OpenAI", "")
                mock_http.assert_awaited_once_with(
                    "identify_person", {"name": "Dave", "organization": "OpenAI", "title": ""}
                )
                return result

        result = asyncio.run(_run())
        self.assertEqual(result["summary"], "http fallback")

    def test_invoke_identify_person_falls_back_to_http_on_timeout_error(self) -> None:
        async def _run() -> dict:
            mock_uagents = AsyncMock(side_effect=TimeoutError("no response"))
            with patch.object(bridge, "_uagents_identify", mock_uagents), patch.object(
                bridge, "invoke_remote_skill", return_value={"summary": "http fallback on timeout", "confidence": "low"}
            ) as mock_http:
                result = await bridge.invoke_identify_person("Eve", "Anthropic", "")
                mock_http.assert_awaited_once()
                return result

        result = asyncio.run(_run())
        self.assertEqual(result["summary"], "http fallback on timeout")

    def test_invoke_identify_person_falls_back_to_http_on_any_exception(self) -> None:
        async def _run() -> dict:
            mock_uagents = AsyncMock(side_effect=ConnectionRefusedError("refused"))
            with patch.object(bridge, "_uagents_identify", mock_uagents), patch.object(
                bridge, "invoke_remote_skill", return_value={"summary": "fallback", "confidence": "low"}
            ) as mock_http:
                result = await bridge.invoke_identify_person("Frank", "Meta", "")
                mock_http.assert_awaited_once()
                return result

        result = asyncio.run(_run())
        self.assertEqual(result["summary"], "fallback")

    # ------------------------------------------------------------------
    # Legacy tests (kept; now exercise the HTTP fallback path indirectly)
    # ------------------------------------------------------------------

    def test_flagship_wrapper_routes_to_identify_person_skill(self) -> None:
        async def _run() -> dict:
            # uagents not installed in test env → RuntimeError → falls back to invoke_remote_skill
            with patch.object(
                bridge,
                "invoke_remote_skill",
                return_value={"summary": "ok", "confidence": "high"},
            ) as mocked:
                result = await bridge.invoke_identify_person("A", "B", "C")
                mocked.assert_awaited_once_with(
                    "identify_person",
                    {"name": "A", "organization": "B", "title": "C"},
                )
                return result

        result = asyncio.run(_run())
        self.assertEqual(result["summary"], "ok")

    def test_remote_skill_uses_agent_address_for_generic_skill_config(self) -> None:
        async def _run() -> None:
            cfg = {"agent_address": "agent1qtest", "timeout_ms": 5000}
            with patch.object(bridge, "load_skill_config", return_value=cfg), patch.object(
                bridge,
                "_invoke_with_retry",
                return_value={"summary": "ok", "confidence": "high"},
            ) as mocked:
                await bridge.invoke_remote_skill(
                    "mail_sending_agent",
                    {"command": "send", "recipient": "b@example.com", "subject": "Hi", "body": "Body"},
                )
                mocked.assert_awaited_once()
                args = mocked.await_args.args
                self.assertEqual(args[0], "http://localhost:8001/v1/chat/completions")
                self.assertEqual(args[1], {"args": {"command": "send", "recipient": "b@example.com", "subject": "Hi", "body": "Body"}, "agent_address": "agent1qtest"})

        asyncio.run(_run())

    def test_later_wrappers_route_to_expected_skill_names(self) -> None:
        async def _run() -> None:
            with patch.object(bridge, "invoke_remote_skill", return_value={"summary": "ok"}) as mocked:
                await bridge.invoke_google_search("latest lahacks updates")
                await bridge.invoke_google_calendar("create", "tomorrow 3pm", "team sync")
                await bridge.invoke_gmail("draft", "a@example.com", "Hello", "Body")
                await bridge.invoke_people_search_agent("Ada Lovelace robotics")
                await bridge.invoke_mail_sending_agent("send", "b@example.com", "Hi", "Body")
                await bridge.invoke_task_scheduling_agent("schedule", "next friday", "design review")
                await bridge.invoke_reminder_agent("remind", "tomorrow 9am", "take meds")
                await bridge.invoke_purchase_agent("buy", "Sony WH-1000XM6", "2")

                expected = [
                    (("google_search", {"query": "latest lahacks updates"}),),
                    (("google_calendar", {"command": "create", "datetime": "tomorrow 3pm", "details": "team sync"}),),
                    (("gmail", {"command": "draft", "recipient": "a@example.com", "subject": "Hello", "body": "Body"}),),
                    (("people_search_agent", {"query": "Ada Lovelace robotics"}),),
                    (("mail_sending_agent", {"command": "send", "recipient": "b@example.com", "subject": "Hi", "body": "Body"}),),
                    (("task_scheduling_agent", {"command": "schedule", "datetime": "next friday", "details": "design review"}),),
                    (("reminder_agent", {"command": "remind", "datetime": "tomorrow 9am", "details": "take meds"}),),
                    (("purchase_agent", {"command": "buy", "item": "Sony WH-1000XM6", "quantity": "2"}),),
                ]
                actual = [call.args for call in mocked.await_args_list]
                self.assertEqual(actual, [item[0] for item in expected])

        asyncio.run(_run())

    def test_fallback_response_covers_new_skills(self) -> None:
        google = bridge._fallback_response("google_search", "timeout")  # noqa: SLF001
        calendar = bridge._fallback_response("google_calendar", "timeout")  # noqa: SLF001
        gmail = bridge._fallback_response("gmail", "timeout")  # noqa: SLF001
        purchase = bridge._fallback_response("purchase_agent", "timeout")  # noqa: SLF001
        people = bridge._fallback_response("people_search_agent", "timeout")  # noqa: SLF001
        reminder = bridge._fallback_response("reminder_agent", "timeout")  # noqa: SLF001

        self.assertIn("Google search", google["summary"])
        self.assertIn("Google Calendar", calendar["summary"])
        self.assertIn("Gmail", gmail["summary"])
        self.assertIn("purchase", purchase["summary"].lower())
        self.assertIn("people", people["summary"].lower())
        self.assertIn("reminder", reminder["summary"].lower())
        self.assertEqual(gmail["confidence"], "low")

    def test_fallback_response_mentions_local_skill_service_when_connection_fails(self) -> None:
        reminder = bridge._fallback_response("reminder_agent", "All connection attempts failed")  # noqa: SLF001

        self.assertIn("localhost:8001", reminder["summary"])
        self.assertEqual(reminder["error"], "All connection attempts failed")

    def test_invoke_remote_skill_uses_skill_timeout_override(self) -> None:
        async def _run() -> None:
            with patch.object(bridge, "load_skill_config", return_value={"timeout_ms": 2500}), patch.object(
                bridge,
                "_invoke_with_retry",
                return_value={"summary": "ok"},
            ) as mocked:
                await bridge.invoke_remote_skill("describe_scene", {"image_context": "desk"})
                self.assertEqual(mocked.await_args.kwargs["timeout_s"], 2.5)

        asyncio.run(_run())

    def test_retry_status_policy(self) -> None:
        self.assertTrue(bridge._should_retry_status(429))  # noqa: SLF001
        self.assertTrue(bridge._should_retry_status(503))  # noqa: SLF001
        self.assertFalse(bridge._should_retry_status(404))  # noqa: SLF001


class ChannelsLazyImportTests(unittest.TestCase):
    def test_backend_channel_importable_via_channels_package(self) -> None:
        from omegaclaw.channels import BackendChannel, GlassesTask  # noqa: F401

        self.assertTrue(callable(BackendChannel))
        self.assertTrue(callable(GlassesTask))

    def test_importing_runtime_loop_does_not_trigger_circular_import(self) -> None:
        from omegaclaw.runtime_loop import OmegaClawAgentLoop  # noqa: F401

        self.assertTrue(callable(OmegaClawAgentLoop))

    def test_glasses_task_to_channel_message_includes_required_keys(self) -> None:
        from omegaclaw.channels.backend_channel import GlassesTask

        task = GlassesTask(
            session_id="s1",
            turn_id="t1",
            intent="who is this",
            tool_call_id="tc1",
            args={"name": "Alice", "organization": "Fetch.ai"},
        )
        msg = task.to_channel_message()
        for key in ("session_id", "turn_id", "intent", "tool_call_id", "args"):
            self.assertIn(key, msg)
        self.assertNotIn("image_b64", msg)

    def test_glasses_task_includes_image_b64_when_set(self) -> None:
        from omegaclaw.channels.backend_channel import GlassesTask

        task = GlassesTask(
            session_id="s1",
            turn_id="t1",
            intent="who is this",
            tool_call_id="tc1",
            args={},
            image_b64="abc123",
        )
        msg = task.to_channel_message()
        self.assertEqual(msg["image_b64"], "abc123")


if __name__ == "__main__":
    unittest.main()
