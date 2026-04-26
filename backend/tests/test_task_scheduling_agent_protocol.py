from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from datetime import UTC, datetime
from uuid import uuid4
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.task_scheduling_agent import (  # noqa: E402
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    ErrorMessage,
    TaskSchedulingRequest,
    TaskSchedulingResponse,
    TextContent,
    normalize_schedule_payload,
    extract_schedule_request,
    handle_message,
    handle_task_scheduling_request,
)


class _FakeLogger:
    def exception(self, *_args, **_kwargs) -> None:
        return None


class _FakeContext:
    def __init__(self) -> None:
        self.logger = _FakeLogger()
        self.sent: list[tuple[str, object]] = []

    async def send(self, sender: str, payload: object) -> None:
        self.sent.append((sender, payload))


class TaskSchedulingAgentProtocolTests(unittest.TestCase):
    def test_normalize_schedule_payload_falls_back_when_zoneinfo_data_missing(self) -> None:
        class _FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                base = cls(2026, 4, 26, 13, 0, 0, tzinfo=UTC)
                if tz is None:
                    return base.replace(tzinfo=None)
                return base.astimezone(tz)

        payload = {
            "summary": "Design review",
            "start_iso": "",
            "end_iso": "",
            "details": "Review the latest mocks",
        }

        with patch(
            "agents.task_scheduling_agent.ZoneInfo",
            side_effect=ZoneInfoNotFoundError("No time zone found with key America/Los_Angeles"),
        ), patch("agents.task_scheduling_agent.datetime", _FakeDateTime):
            normalized = normalize_schedule_payload(
                "Schedule a design review today at 10 AM",
                payload,
                "America/Los_Angeles",
            )

        self.assertEqual(normalized["start_iso"], "2026-04-26T10:00:00")
        self.assertEqual(normalized["end_iso"], "2026-04-26T11:00:00")

    def test_normalize_schedule_payload_resolves_today_locally(self) -> None:
        payload = {
            "summary": "Design review",
            "start_iso": "2025-01-09T10:00:00",
            "end_iso": "2025-01-09T11:00:00",
            "details": "Review the latest mocks",
        }

        with patch("agents.task_scheduling_agent._now_in_timezone", return_value=datetime(2026, 4, 26, 6, 0, 0)):
            normalized = normalize_schedule_payload(
                "Schedule a design review today at 10 AM",
                payload,
                "America/Los_Angeles",
            )

        self.assertEqual(normalized["start_iso"], "2026-04-26T10:00:00")
        self.assertEqual(normalized["end_iso"], "2026-04-26T11:00:00")

    def test_normalize_schedule_payload_resolves_tomorrow_locally(self) -> None:
        payload = {
            "summary": "Design review",
            "start_iso": "",
            "end_iso": "",
            "details": "Review the latest mocks",
        }

        with patch("agents.task_scheduling_agent._now_in_timezone", return_value=datetime(2026, 4, 26, 6, 0, 0)):
            normalized = normalize_schedule_payload(
                "Schedule a design review tomorrow at 3 PM",
                payload,
                "America/Los_Angeles",
            )

        self.assertEqual(normalized["start_iso"], "2026-04-27T15:00:00")
        self.assertEqual(normalized["end_iso"], "2026-04-27T16:00:00")

    def test_extract_schedule_request_handles_code_fenced_json(self) -> None:
        class _FakeCompletions:
            @staticmethod
            def create(**_kwargs):
                return type(
                    "Resp",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {
                                    "message": type(
                                        "Message",
                                        (),
                                        {
                                            "content": "```json\n{\"summary\":\"Design review\",\"start_iso\":\"2026-04-27T10:00:00Z\",\"end_iso\":\"2026-04-27T10:30:00Z\",\"details\":\"Review the latest mocks\"}\n```"
                                        },
                                    )()
                                },
                            )()
                        ]
                    },
                )()

        fake_client = type(
            "Client",
            (),
            {"chat": type("Chat", (), {"completions": _FakeCompletions()})()},
        )()

        payload = extract_schedule_request("Schedule a design review tomorrow at 10", client=fake_client)

        self.assertEqual(payload["summary"], "Design review")
        self.assertEqual(payload["start_iso"], "2026-04-27T10:00:00Z")

    def test_handle_message_acknowledges_and_returns_successful_chat_response(self) -> None:
        ctx = _FakeContext()
        msg = ChatMessage(
            timestamp=None,
            msg_id=uuid4(),
            content=[TextContent(type="text", text="Schedule a design review tomorrow at 10")],
        )

        async def _run() -> None:
            with patch(
                "agents.task_scheduling_agent.extract_schedule_request",
                return_value={
                    "summary": "Design review",
                    "start_iso": "2026-04-27T10:00:00Z",
                    "end_iso": "2026-04-27T10:30:00Z",
                    "details": "Review the latest mocks",
                },
            ), patch(
                "agents.task_scheduling_agent.create_calendar_event",
                return_value={
                    "event_id": "event-id-1",
                    "calendar_id": "reed@poweredbyhue.com",
                    "calendar_tz": "America/Los_Angeles",
                    "start": {"dateTime": "2026-04-27T10:00:00", "timeZone": "America/Los_Angeles"},
                    "end": {"dateTime": "2026-04-27T10:30:00", "timeZone": "America/Los_Angeles"},
                },
            ):
                await handle_message(ctx, "sender-1", msg)

        asyncio.run(_run())

        self.assertEqual(len(ctx.sent), 2)
        self.assertIsInstance(ctx.sent[0][1], ChatAcknowledgement)
        response = ctx.sent[1][1]
        self.assertIsInstance(response, ChatMessage)
        self.assertTrue(any(isinstance(item, EndSessionContent) for item in response.content))
        text_parts = [item.text for item in response.content if isinstance(item, TextContent)]
        self.assertTrue(any("scheduled" in part.lower() for part in text_parts))
        self.assertTrue(any("reed@poweredbyhue.com" in part for part in text_parts))
        self.assertTrue(any("event-id-1" in part for part in text_parts))

    def test_handle_task_scheduling_request_returns_structured_success_response(self) -> None:
        ctx = _FakeContext()
        msg = TaskSchedulingRequest(prompt="Schedule a design review tomorrow at 10")

        async def _run() -> None:
            with patch(
                "agents.task_scheduling_agent.extract_schedule_request",
                return_value={
                    "summary": "Design review",
                    "start_iso": "2026-04-27T10:00:00Z",
                    "end_iso": "2026-04-27T10:30:00Z",
                    "details": "Review the latest mocks",
                },
            ), patch(
                "agents.task_scheduling_agent.create_calendar_event",
                return_value={
                    "event_id": "event-id-1",
                    "calendar_id": "reed@poweredbyhue.com",
                    "calendar_tz": "America/Los_Angeles",
                    "start": {"dateTime": "2026-04-27T10:00:00", "timeZone": "America/Los_Angeles"},
                    "end": {"dateTime": "2026-04-27T10:30:00", "timeZone": "America/Los_Angeles"},
                },
            ):
                await handle_task_scheduling_request(ctx, "sender-2", msg)

        asyncio.run(_run())

        response = ctx.sent[0][1]
        self.assertIsInstance(response, TaskSchedulingResponse)
        self.assertEqual(response.summary, "Design review")
        self.assertEqual(response.event_id, "event-id-1")
        self.assertIn("scheduled", response.status.lower())

    def test_handle_task_scheduling_request_returns_error_when_summary_missing(self) -> None:
        ctx = _FakeContext()
        msg = TaskSchedulingRequest(prompt="Schedule something tomorrow")

        async def _run() -> None:
            with patch(
                "agents.task_scheduling_agent.extract_schedule_request",
                return_value={
                    "summary": "",
                    "start_iso": "2026-04-27T10:00:00Z",
                    "end_iso": "2026-04-27T10:30:00Z",
                    "details": "",
                },
            ):
                await handle_task_scheduling_request(ctx, "sender-3", msg)

        asyncio.run(_run())

        response = ctx.sent[0][1]
        self.assertIsInstance(response, ErrorMessage)
        self.assertIn("summary", response.error.lower())


if __name__ == "__main__":
    unittest.main()
