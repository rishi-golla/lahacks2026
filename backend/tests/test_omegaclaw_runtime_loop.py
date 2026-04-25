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
        self.assertEqual(classify("Schedule a meeting tomorrow", {}), "google_calendar")
        self.assertEqual(classify("Draft email to team", {}), "gmail")
        self.assertEqual(classify("Do something unknown", {}), "unknown")

    def test_run_once_dispatches_known_skill_and_sends_response(self) -> None:
        loop = OmegaClawAgentLoop()
        inbound = {
            "request_id": "req-1",
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
                self.assertEqual(payload["skill_name"], "google_search")
                self.assertEqual(payload["result"]["summary"], "ok")
                return did_work

        self.assertTrue(asyncio.run(_run()))

    def test_run_once_handles_unknown_skill_without_remote_call(self) -> None:
        loop = OmegaClawAgentLoop()
        inbound = {
            "request_id": "req-2",
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

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
