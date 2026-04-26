from __future__ import annotations

import base64
import email
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.mail_sending_agent import send_gmail_message  # noqa: E402


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class MailSendingAgentGmailSendTests(unittest.TestCase):
    @patch.dict(
        "os.environ",
        {
            "GMAIL_SENDER_EMAIL": "rishi@example.com",
            "GMAIL_CLIENT_ID": "client-id",
            "GMAIL_CLIENT_SECRET": "client-secret",
            "GMAIL_REFRESH_TOKEN": "refresh-token",
        },
        clear=False,
    )
    @patch("agents.mail_sending_agent.requests.post")
    def test_send_gmail_message_refreshes_token_and_sends_html_mime(self, mocked_post) -> None:
        mocked_post.side_effect = [
            _FakeResponse({"access_token": "access-token"}),
            _FakeResponse({"id": "gmail-message-id-123"}),
        ]

        message_id = send_gmail_message(
            recipient="sarah@example.com",
            subject="Orbiting thanks",
            html_body="<p>Hello Sarah</p>",
        )

        self.assertEqual(message_id, "gmail-message-id-123")
        self.assertEqual(mocked_post.call_count, 2)

        refresh_call = mocked_post.call_args_list[0]
        self.assertIn("oauth2.googleapis.com/token", refresh_call.args[0])

        send_call = mocked_post.call_args_list[1]
        self.assertIn("gmail.googleapis.com/gmail/v1/users/me/messages/send", send_call.args[0])
        raw_message = send_call.kwargs["json"]["raw"]
        decoded = base64.urlsafe_b64decode(raw_message + "=" * (-len(raw_message) % 4))
        parsed = email.message_from_bytes(decoded)
        self.assertIn("Orbiting thanks", parsed["Subject"])
        payload = parsed.get_payload(decode=True).decode()
        self.assertIn("<p>Hello Sarah</p>", payload)
        self.assertIn("text/html", parsed.as_string())


if __name__ == "__main__":
    unittest.main()
