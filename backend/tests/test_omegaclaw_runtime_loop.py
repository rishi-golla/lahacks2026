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

from omegaclaw.runtime_loop import OmegaClawAgentLoop  # noqa: E402


class OmegaClawRuntimeLoopTests(unittest.TestCase):
    def test_classifier_covers_new_and_flagship_skills(self) -> None:
        classify = OmegaClawAgentLoop._classify

        self.assertEqual(classify("Who is this person?", {}), "identify_person")
        self.assertEqual(classify("Describe what I see", {}), "describe_scene")
        self.assertEqual(classify("Google search for LAHacks updates", {}), "google_search")
        self.assertEqual(classify("Schedule a meeting tomorrow", {}), "task_scheduling_agent")
        self.assertEqual(classify("Draft email to team", {}), "mail_sending_agent")
        self.assertEqual(classify("Find this person from Stripe", {}), "people_search_agent")
        self.assertEqual(classify("Remind me tomorrow to stretch", {}), "reminder_agent")
        self.assertEqual(classify("Buy new headphones", {}), "purchase_agent")
        self.assertEqual(classify("Do something unknown", {}), "unknown")

    def test_run_once_dispatches_known_skill_and_sends_response(self) -> None:
        loop = OmegaClawAgentLoop()
        inbound = {
            "request_id": "req-1",
            "tool_call_id": "tc-1",
            "intent": "google this",
            "args": {"query": "latest fetch ai news"},
        }

        async def _run() -> bool:
            mocked_remote = AsyncMock(return_value={"summary": "ok", "confidence": "high"})
            with patch("omegaclaw.runtime_loop.my_backend.getLastMessage", return_value=inbound), patch(
                "omegaclaw.runtime_loop.invoke_remote_skill", mocked_remote
            ), patch("omegaclaw.runtime_loop.my_backend.send_message") as mocked_send:
                did_work = await loop.run_once()
                mocked_remote.assert_awaited_once_with(
                    skill_name="google_search",
                    args={"query": "latest fetch ai news"},
                )
                self.assertTrue(mocked_send.called)
                payload = json.loads(mocked_send.call_args.args[0])
                self.assertEqual(payload["request_id"], "req-1")
                self.assertEqual(payload["tool_call_id"], "tc-1")
                self.assertEqual(payload["skill_name"], "google_search")
                self.assertEqual(payload["result"]["summary"], "ok")
                self.assertEqual(payload["events"][0]["phase"], "started")
                self.assertEqual(payload["events"][1]["phase"], "result")
                return did_work

        self.assertTrue(asyncio.run(_run()))

    def test_run_once_populates_reminder_command_from_intent_when_args_missing(self) -> None:
        loop = OmegaClawAgentLoop()
        inbound = {
            "request_id": "req-reminder",
            "tool_call_id": "tc-reminder",
            "intent": "Remind me tomorrow at 9 to stretch",
            "args": {},
        }

        async def _run() -> None:
            mocked_shim = AsyncMock(return_value={"summary": "ok", "confidence": "high"})
            with patch("omegaclaw.runtime_loop.my_backend.getLastMessage", return_value=inbound), patch(
                "omegaclaw.runtime_loop.invoke_local_skill_shim", mocked_shim
            ), patch("omegaclaw.runtime_loop.my_backend.send_message"):
                did_work = await loop.run_once()
                self.assertTrue(did_work)
                mocked_shim.assert_awaited_once_with(
                    skill_name="reminder_agent",
                    args={
                        "command": "Remind me tomorrow at 9 to stretch",
                        "datetime": "",
                        "details": "",
                    },
                )

        asyncio.run(_run())

    def test_run_once_uses_local_shim_for_reminder_agent(self) -> None:
        loop = OmegaClawAgentLoop()
        inbound = {
            "request_id": "req-reminder-local",
            "tool_call_id": "tc-reminder-local",
            "intent": "Remind me in 5 seconds to stretch",
            "args": {},
        }

        async def _run() -> None:
            mocked_shim = AsyncMock(return_value={"summary": "Done", "confidence": "high"})
            mocked_remote = AsyncMock(return_value={"summary": "should-not-run"})
            with patch("omegaclaw.runtime_loop.my_backend.getLastMessage", return_value=inbound), patch(
                "omegaclaw.runtime_loop.invoke_local_skill_shim", mocked_shim
            ), patch("omegaclaw.runtime_loop.invoke_remote_skill", mocked_remote), patch(
                "omegaclaw.runtime_loop.my_backend.send_message"
            ):
                did_work = await loop.run_once()
                self.assertTrue(did_work)
                mocked_shim.assert_awaited_once()
                mocked_remote.assert_not_awaited()

        asyncio.run(_run())

    def test_run_once_uses_local_shim_for_mail_sending_agent(self) -> None:
        loop = OmegaClawAgentLoop()
        inbound = {
            "request_id": "req-mail-local",
            "tool_call_id": "tc-mail-local",
            "intent": "Email Sarah and thank her",
            "args": {},
        }

        async def _run() -> None:
            mocked_shim = AsyncMock(return_value={"summary": "Done", "confidence": "high"})
            mocked_remote = AsyncMock(return_value={"summary": "should-not-run"})
            with patch("omegaclaw.runtime_loop.my_backend.getLastMessage", return_value=inbound), patch(
                "omegaclaw.runtime_loop.invoke_local_skill_shim", mocked_shim
            ), patch("omegaclaw.runtime_loop.invoke_remote_skill", mocked_remote), patch(
                "omegaclaw.runtime_loop.my_backend.send_message"
            ):
                did_work = await loop.run_once()
                self.assertTrue(did_work)
                mocked_shim.assert_awaited_once_with(
                    skill_name="mail_sending_agent",
                    args={
                        "command": "Email Sarah and thank her",
                        "recipient": "",
                        "subject": "",
                        "body": "",
                    },
                )
                mocked_remote.assert_not_awaited()

        asyncio.run(_run())

    def test_run_once_uses_local_shim_for_flagship_identify_person(self) -> None:
        loop = OmegaClawAgentLoop()
        inbound = {
            "request_id": "req-shim",
            "tool_call_id": "tc-shim",
            "intent": "Who is this?",
            "args": {"name": "Sam"},
        }

        async def _run() -> None:
            mocked_shim = AsyncMock(return_value={"summary": "Sam is...", "confidence": "high"})
            mocked_remote = AsyncMock(return_value={"summary": "should-not-run"})
            with patch("omegaclaw.runtime_loop.my_backend.getLastMessage", return_value=inbound), patch(
                "omegaclaw.runtime_loop.invoke_local_skill_shim", mocked_shim
            ), patch("omegaclaw.runtime_loop.invoke_remote_skill", mocked_remote), patch(
                "omegaclaw.runtime_loop.my_backend.send_message"
            ):
                did_work = await loop.run_once()
                self.assertTrue(did_work)
                mocked_shim.assert_awaited_once_with(skill_name="identify_person", args={"name": "Sam"})
                mocked_remote.assert_not_awaited()

        asyncio.run(_run())

    def test_run_once_handles_unknown_skill_without_remote_call(self) -> None:
        loop = OmegaClawAgentLoop()
        inbound = {
            "request_id": "req-2",
            "tool_call_id": "tc-2",
            "intent": "sing a song",
            "args": {},
        }

        async def _run() -> None:
            mocked_remote = AsyncMock(return_value={"summary": "should-not-run"})
            with patch("omegaclaw.runtime_loop.my_backend.getLastMessage", return_value=inbound), patch(
                "omegaclaw.runtime_loop.invoke_remote_skill", mocked_remote
            ), patch("omegaclaw.runtime_loop.my_backend.send_message") as mocked_send:
                did_work = await loop.run_once()
                self.assertTrue(did_work)
                mocked_remote.assert_not_awaited()
                payload = json.loads(mocked_send.call_args.args[0])
                self.assertEqual(payload["skill_name"], "unknown")
                self.assertEqual(payload["result"]["source"], "omegaclaw:no_match")
                self.assertEqual(payload["events"][1]["phase"], "error")
                self.assertEqual(payload["events"][1]["error"], "no_matching_skill")

        asyncio.run(_run())

    def test_run_once_handles_explicit_unsupported_skill_name_as_no_match(self) -> None:
        loop = OmegaClawAgentLoop()
        inbound = {
            "request_id": "req-3",
            "tool_call_id": "tc-3",
            "intent": "whatever",
            "skill_name": "unsupported_skill",
            "args": {},
        }

        async def _run() -> None:
            mocked_remote = AsyncMock(return_value={"summary": "should-not-run"})
            with patch("omegaclaw.runtime_loop.my_backend.getLastMessage", return_value=inbound), patch(
                "omegaclaw.runtime_loop.invoke_remote_skill", mocked_remote
            ), patch("omegaclaw.runtime_loop.my_backend.send_message") as mocked_send:
                did_work = await loop.run_once()
                self.assertTrue(did_work)
                mocked_remote.assert_not_awaited()
                payload = json.loads(mocked_send.call_args.args[0])
                self.assertEqual(payload["skill_name"], "unsupported_skill")
                self.assertEqual(payload["result"]["source"], "omegaclaw:no_match")
                self.assertEqual(payload["events"][1]["phase"], "error")

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
