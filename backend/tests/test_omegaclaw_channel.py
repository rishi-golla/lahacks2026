from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from omegaclaw.channels.backend_channel import BackendChannel, GlassesTask  # noqa: E402
from omegaclaw.channels import my_backend  # noqa: E402


class OmegaClawChannelTests(unittest.TestCase):
    def test_backend_channel_routes_through_single_loop_and_returns_result(self) -> None:
        task = GlassesTask(
            session_id="session-1",
            turn_id="turn-1",
            intent="Who is this?",
            tool_call_id="tool-1",
            args={"name": "Sarah Chen", "organization": "Fetch.ai", "title": "CTO"},
        )

        async def _run() -> dict:
            channel = BackendChannel()
            with patch(
                "omegaclaw.runtime_loop.invoke_remote_skill",
                return_value={
                    "summary": "Sarah Chen is CTO at Fetch.ai.",
                    "confidence": "high",
                    "source": "agentverse:identify_person",
                },
            ):
                return await channel.submit(task)

        result = asyncio.run(_run())
        self.assertEqual(result["confidence"], "high")
        self.assertIn("Sarah Chen", result["summary"])

    def test_channel_contract_queue_roundtrip(self) -> None:
        my_backend.start_my_backend(backend_url="ws://localhost")

        async def _run() -> None:
            request_id, future = my_backend.enqueue_message({"intent": "describe this"})
            queued = my_backend.getLastMessage()
            assert queued is not None
            self.assertEqual(queued["request_id"], request_id)

            my_backend.send_message(
                '{"request_id": "%s", "result": {"summary": "ok", "confidence": "high"}}'
                % request_id
            )
            resolved = await future
            self.assertEqual(resolved["result"]["summary"], "ok")

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
