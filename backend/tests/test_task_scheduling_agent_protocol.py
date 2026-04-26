from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


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
    def test_handle_message_acknowledges_and_returns_successful_chat_response(self) -> None:
        ctx = _FakeContext()
        msg = ChatMessage(
            timestamp=None,
            msg_id="msg-1",
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
                return_value="event-id-1",
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
                return_value="event-id-1",
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
