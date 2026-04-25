from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from omegaclaw.protocol import make_loop_response, make_tool_event, result_to_gemini_tool_response  # noqa: E402


class OmegaClawProtocolTests(unittest.TestCase):
    def test_make_tool_event_validates_phase(self) -> None:
        with self.assertRaises(ValueError):
            make_tool_event("tc-1", "identify_person", "bad-phase")

    def test_make_loop_response_includes_started_and_result_events(self) -> None:
        payload = make_loop_response(
            request_id="req-1",
            tool_call_id="tc-1",
            skill_name="identify_person",
            result={"summary": "done", "confidence": "high"},
            args={"name": "A"},
        )
        self.assertEqual(payload["request_id"], "req-1")
        self.assertEqual(payload["tool_call_id"], "tc-1")
        self.assertEqual(payload["events"][0]["phase"], "started")
        self.assertEqual(payload["events"][1]["phase"], "result")

    def test_result_to_gemini_response_uses_passed_tool_name(self) -> None:
        payload = result_to_gemini_tool_response(
            tool_call_id="tc-99",
            tool_name="google_search",
            result={"summary": "Found results"},
        )
        self.assertEqual(payload["tool_response"]["id"], "tc-99")
        self.assertEqual(payload["tool_response"]["name"], "google_search")


if __name__ == "__main__":
    unittest.main()
