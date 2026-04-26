from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.reminder_agent import (  # noqa: E402
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    ErrorMessage,
    ReminderRequest,
    ReminderResponse,
    TextContent,
    extract_reminder_request,
    handle_message,
    handle_reminder_request,
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


class ReminderAgentProtocolTests(unittest.TestCase):
    def test_extract_reminder_request_falls_back_without_asi_key(self) -> None:
        with patch("agents.reminder_core._get_asi_client", side_effect=RuntimeError("Missing required environment variable: ASI1_API_KEY")):
            payload = extract_reminder_request("Remind me in 5 seconds to stretch")

        self.assertEqual(payload["details"], "stretch")
        self.assertIn("in 5 seconds", payload["datetime"])

    def test_handle_message_acknowledges_and_returns_spoken_confirmation(self) -> None:
        ctx = _FakeContext()
        msg = ChatMessage(
            timestamp=None,
            msg_id=uuid4(),
            content=[TextContent(type="text", text="Remind me tomorrow at 9 to stretch")],
        )

        async def _run() -> None:
            with patch(
                "agents.reminder_agent.extract_reminder_request",
                return_value={"datetime": "tomorrow at 9", "details": "stretch"},
            ):
                await handle_message(ctx, "sender-1", msg)

        asyncio.run(_run())

        self.assertEqual(len(ctx.sent), 2)
        self.assertIsInstance(ctx.sent[0][1], ChatAcknowledgement)
        response = ctx.sent[1][1]
        self.assertIsInstance(response, ChatMessage)
        self.assertTrue(any(isinstance(item, EndSessionContent) for item in response.content))
        text_parts = [item.text for item in response.content if isinstance(item, TextContent)]
        self.assertTrue(any("reminder" in part.lower() for part in text_parts))

    def test_handle_reminder_request_returns_structured_response(self) -> None:
        ctx = _FakeContext()
        msg = ReminderRequest(prompt="Remind me tomorrow at 9 to stretch")

        async def _run() -> None:
            with patch(
                "agents.reminder_agent.extract_reminder_request",
                return_value={"datetime": "tomorrow at 9", "details": "stretch"},
            ):
                await handle_reminder_request(ctx, "sender-2", msg)

        asyncio.run(_run())

        self.assertEqual(len(ctx.sent), 1)
        response = ctx.sent[0][1]
        self.assertIsInstance(response, ReminderResponse)
        self.assertEqual(response.datetime, "tomorrow at 9")
        self.assertEqual(response.details, "stretch")
        self.assertIn("set", response.status.lower())

    def test_handle_reminder_request_returns_error_when_details_missing(self) -> None:
        ctx = _FakeContext()
        msg = ReminderRequest(prompt="Remind me tomorrow")

        async def _run() -> None:
            with patch(
                "agents.reminder_agent.extract_reminder_request",
                return_value={"datetime": "tomorrow", "details": ""},
            ):
                await handle_reminder_request(ctx, "sender-3", msg)

        asyncio.run(_run())

        response = ctx.sent[0][1]
        self.assertIsInstance(response, ErrorMessage)
        self.assertIn("details", response.error.lower())


if __name__ == "__main__":
    unittest.main()
