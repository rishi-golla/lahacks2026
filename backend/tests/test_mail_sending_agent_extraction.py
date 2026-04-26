from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.mail_sending_agent import extract_email_request  # noqa: E402


class MailSendingAgentExtractionTests(unittest.TestCase):
    def test_extract_email_request_returns_structured_fields(self) -> None:
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **_: SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(
                                    content=(
                                        '{"recipient":"sarah@example.com",'
                                        '"subject_hint":"thank you",'
                                        '"body_intent":"thank Sarah for meeting today"}'
                                    )
                                )
                            )
                        ]
                    )
                )
            )
        )

        result = extract_email_request(
            "Send Sarah an email thanking her for meeting today.",
            client=fake_client,
        )

        self.assertEqual(result["recipient"], "sarah@example.com")
        self.assertEqual(result["subject_hint"], "thank you")
        self.assertEqual(result["body_intent"], "thank Sarah for meeting today")


if __name__ == "__main__":
    unittest.main()
