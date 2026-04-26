from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.mail_sending_agent import build_html_email  # noqa: E402


class MailSendingAgentFormattingTests(unittest.TestCase):
    def test_build_html_email_includes_required_signature_elements(self) -> None:
        subject, body = build_html_email(
            {
                "subject_hint": "thank Sarah for meeting",
                "body_intent": "Say thanks for meeting today and that I appreciated the conversation.",
            }
        )

        self.assertTrue(subject)
        self.assertIn("<p>", body)
        self.assertIn("Rishi Golla", body)
        self.assertIn("Sent by Edith, my AI Agent", body)
        self.assertIn(
            "https://res.cloudinary.com/fetch-ai/image/upload/v1775063969/fetch-llm/onboarding/4_mkezrr.png",
            body,
        )
        self.assertIn("www.asi1.ai", body)


if __name__ == "__main__":
    unittest.main()
