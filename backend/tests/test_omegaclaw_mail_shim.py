from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from omegaclaw.skills.shims import invoke_local_skill_shim  # noqa: E402


class OmegaClawMailShimTests(unittest.TestCase):
    def test_invoke_local_mail_shim_prefers_explicit_args(self) -> None:
        async def _run() -> dict:
            with patch(
                "omegaclaw.skills.shims.send_gmail_message",
                return_value="gmail-msg-1",
            ) as mocked_send, patch(
                "omegaclaw.skills.shims.build_html_email",
                return_value=("Launch Update", "<p>Ship it</p>"),
            ) as mocked_build, patch(
                "omegaclaw.skills.shims.extract_email_request"
            ) as mocked_extract:
                result = await invoke_local_skill_shim(
                    skill_name="mail_sending_agent",
                    args={
                        "command": "ignore me",
                        "recipient": "sarah@example.com",
                        "subject": "Launch Update",
                        "body": "Ship it",
                    },
                )
                mocked_send.assert_called_once_with(
                    recipient="sarah@example.com",
                    subject="Launch Update",
                    html_body="<p>Ship it</p>",
                )
                mocked_build.assert_called_once()
                mocked_extract.assert_not_called()
                return result

        result = asyncio.run(_run())
        self.assertEqual(result["source"], "local:mail_sending_agent")
        self.assertEqual(result["recipient"], "sarah@example.com")
        self.assertEqual(result["message_id"], "gmail-msg-1")

    def test_invoke_local_mail_shim_can_parse_command_when_explicit_args_missing(self) -> None:
        async def _run() -> dict:
            with patch(
                "omegaclaw.skills.shims.extract_email_request",
                return_value={
                    "recipient": "sarah@example.com",
                    "subject_hint": "thank you",
                    "body_intent": "thank Sarah for the intro",
                },
            ) as mocked_extract, patch(
                "omegaclaw.skills.shims.build_html_email",
                return_value=("Thanks", "<p>Thank you</p>"),
            ), patch(
                "omegaclaw.skills.shims.send_gmail_message",
                return_value="gmail-msg-2",
            ):
                result = await invoke_local_skill_shim(
                    skill_name="mail_sending_agent",
                    args={
                        "command": "Email Sarah and thank her for the intro",
                        "recipient": "",
                        "subject": "",
                        "body": "",
                    },
                )
                mocked_extract.assert_called_once_with("Email Sarah and thank her for the intro")
                return result

        result = asyncio.run(_run())
        self.assertEqual(result["recipient"], "sarah@example.com")
        self.assertEqual(result["message_id"], "gmail-msg-2")

    def test_invoke_local_mail_shim_requests_recipient_when_missing(self) -> None:
        async def _run() -> dict:
            with patch(
                "omegaclaw.skills.shims.extract_email_request",
                return_value={"recipient": "", "subject_hint": "", "body_intent": ""},
            ):
                return await invoke_local_skill_shim(
                    skill_name="mail_sending_agent",
                    args={"command": "Send an email saying hi", "recipient": "", "subject": "", "body": ""},
                )

        result = asyncio.run(_run())
        self.assertIn("who should i send", result["summary"].lower())
        self.assertEqual(result["source"], "local:mail_sending_agent")


if __name__ == "__main__":
    unittest.main()
