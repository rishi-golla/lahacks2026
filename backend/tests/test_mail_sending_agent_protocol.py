from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.mail_sending_agent import (  # noqa: E402
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    ErrorMessage,
    MailSendingRequest,
    MailSendingResponse,
    TextContent,
    handle_mail_sending_request,
    handle_message,
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


class MailSendingAgentProtocolTests(unittest.TestCase):
    def test_handle_message_acknowledges_and_returns_successful_chat_response(self) -> None:
        ctx = _FakeContext()
        msg = ChatMessage(
            timestamp=None,
            msg_id=uuid4(),
            content=[TextContent(type="text", text="Send Sarah an email saying hi")],
        )

        async def _run() -> None:
            with patch(
                "agents.mail_sending_agent.extract_email_request",
                return_value={
                    "recipient": "sarah@example.com",
                    "subject_hint": "say hi",
                    "body_intent": "say hi to Sarah",
                },
            ), patch(
                "agents.mail_sending_agent.send_gmail_message",
                return_value="gmail-id-1",
            ):
                await handle_message(ctx, "sender-1", msg)

        asyncio.run(_run())

        self.assertEqual(len(ctx.sent), 2)
        self.assertIsInstance(ctx.sent[0][1], ChatAcknowledgement)
        response = ctx.sent[1][1]
        self.assertIsInstance(response, ChatMessage)
        self.assertTrue(any(isinstance(item, EndSessionContent) for item in response.content))
        text_parts = [item.text for item in response.content if isinstance(item, TextContent)]
        self.assertTrue(any("sent the email" in part.lower() for part in text_parts))

    def test_handle_message_requests_clarification_when_recipient_missing(self) -> None:
        ctx = _FakeContext()
        msg = ChatMessage(
            timestamp=None,
            msg_id=uuid4(),
            content=[TextContent(type="text", text="Send an email saying hi")],
        )

        async def _run() -> None:
            with patch(
                "agents.mail_sending_agent.extract_email_request",
                return_value={
                    "recipient": "",
                    "subject_hint": "say hi",
                    "body_intent": "say hi",
                },
            ):
                await handle_message(ctx, "sender-1", msg)

        asyncio.run(_run())

        response = ctx.sent[1][1]
        text_parts = [item.text for item in response.content if isinstance(item, TextContent)]
        self.assertTrue(any("who should i send" in part.lower() for part in text_parts))

    def test_handle_mail_sending_request_returns_structured_success_response(self) -> None:
        ctx = _FakeContext()
        msg = MailSendingRequest(prompt="Send Sarah an email saying hi")

        async def _run() -> None:
            with patch(
                "agents.mail_sending_agent.extract_email_request",
                return_value={
                    "recipient": "sarah@example.com",
                    "subject_hint": "say hi",
                    "body_intent": "say hi to Sarah",
                },
            ), patch(
                "agents.mail_sending_agent.send_gmail_message",
                return_value="gmail-id-1",
            ):
                await handle_mail_sending_request(ctx, "sender-2", msg)

        asyncio.run(_run())

        self.assertEqual(len(ctx.sent), 1)
        response = ctx.sent[0][1]
        self.assertIsInstance(response, MailSendingResponse)
        self.assertEqual(response.recipient, "sarah@example.com")
        self.assertEqual(response.message_id, "gmail-id-1")
        self.assertIn("sent", response.status.lower())

    def test_handle_mail_sending_request_returns_error_when_recipient_missing(self) -> None:
        ctx = _FakeContext()
        msg = MailSendingRequest(prompt="Send an email saying hi")

        async def _run() -> None:
            with patch(
                "agents.mail_sending_agent.extract_email_request",
                return_value={
                    "recipient": "",
                    "subject_hint": "say hi",
                    "body_intent": "say hi",
                },
            ):
                await handle_mail_sending_request(ctx, "sender-3", msg)

        asyncio.run(_run())

        self.assertEqual(len(ctx.sent), 1)
        response = ctx.sent[0][1]
        self.assertIsInstance(response, ErrorMessage)
        self.assertIn("recipient", response.error.lower())


if __name__ == "__main__":
    unittest.main()
