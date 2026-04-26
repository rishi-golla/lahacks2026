from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from omegaclaw.remote import agentverse_bridge as bridge  # noqa: E402


class RemoteBridgeTests(unittest.TestCase):
    def test_flagship_wrapper_routes_to_identify_person_skill(self) -> None:
        async def _run() -> dict:
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


if __name__ == "__main__":
    unittest.main()
