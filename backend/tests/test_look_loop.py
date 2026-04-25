from __future__ import annotations

import unittest

from app.session.protocol import PhotoFrame, PhotoTrigger

from app.session.look_loop import (
    DEFAULT_LOOK_TIMEOUT_MS,
    LookLoop,
    LookLoopState,
    UnknownLookRequestError,
)


class LookLoopTests(unittest.TestCase):
    def test_create_request_tracks_pending_request_and_client_payload(self) -> None:
        loop = LookLoop()

        request = loop.create_request(
            tool_call_id="tool-1",
            reason="Need a fresh view of the badge",
            requested_at_ms=1_000,
        )

        self.assertEqual(request.state, LookLoopState.PENDING)
        self.assertEqual(request.timeout_ms, DEFAULT_LOOK_TIMEOUT_MS)
        self.assertEqual(request.deadline_ms, 1_000 + DEFAULT_LOOK_TIMEOUT_MS)
        self.assertEqual(
            request.to_client_payload(),
            {
                "type": "look_request",
                "tool_call_id": "tool-1",
                "reason": "Need a fresh view of the badge",
            },
        )
        self.assertEqual(loop.pending_tool_call_ids(), ("tool-1",))

    def test_create_request_allows_timeout_override(self) -> None:
        loop = LookLoop()

        request = loop.create_request(
            tool_call_id="tool-2",
            reason="Closer photo please",
            requested_at_ms=2_000,
            timeout_ms=750,
        )

        self.assertEqual(request.timeout_ms, 750)
        self.assertEqual(request.deadline_ms, 2_750)

    def test_complete_request_with_matching_photo_marks_request_fulfilled(self) -> None:
        loop = LookLoop()
        loop.create_request(
            tool_call_id="tool-3",
            reason="Check the booth sign",
            requested_at_ms=3_000,
        )

        resolved = loop.complete_request(
            PhotoFrame(
                jpeg_b64="/9j/",
                trigger=PhotoTrigger.TOOL_LOOK,
                tool_call_id="tool-3",
                ts_ms=3_125,
            )
        )

        self.assertEqual(resolved.state, LookLoopState.FULFILLED)
        self.assertEqual(resolved.photo_jpeg_b64, "/9j/")
        self.assertEqual(resolved.photo_ts_ms, 3_125)
        self.assertFalse(loop.has_pending_request("tool-3"))

    def test_complete_request_rejects_unknown_tool_call_id(self) -> None:
        loop = LookLoop()

        with self.assertRaises(UnknownLookRequestError):
            loop.complete_request(
                PhotoFrame(
                    jpeg_b64="/9j/",
                    trigger=PhotoTrigger.TOOL_LOOK,
                    tool_call_id="missing",
                    ts_ms=4_000,
                )
            )

    def test_complete_request_requires_tool_call_photo_context(self) -> None:
        loop = LookLoop()
        loop.create_request(
            tool_call_id="tool-4",
            reason="Need a closer look",
            requested_at_ms=4_000,
        )

        with self.assertRaises(ValueError):
            loop.complete_request(
                PhotoFrame(
                    jpeg_b64="/9j/",
                    trigger=PhotoTrigger.USER_REQUEST,
                    tool_call_id="tool-4",
                    ts_ms=4_100,
                )
            )

        with self.assertRaises(ValueError):
            loop.complete_request(
                PhotoFrame(
                    jpeg_b64="/9j/",
                    trigger=PhotoTrigger.TOOL_LOOK,
                    tool_call_id=None,
                    ts_ms=4_200,
                )
            )

    def test_expire_requests_marks_overdue_request_timed_out(self) -> None:
        loop = LookLoop()
        loop.create_request(
            tool_call_id="tool-5",
            reason="Wait for timeout",
            requested_at_ms=5_000,
            timeout_ms=100,
        )

        expired = loop.expire_requests(now_ms=5_099)
        self.assertEqual(expired, [])

        expired = loop.expire_requests(now_ms=5_100)
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0].state, LookLoopState.TIMED_OUT)
        self.assertEqual(expired[0].failure_reason, "look request timed out")
        self.assertFalse(loop.has_pending_request("tool-5"))

    def test_fail_and_cancel_surface_terminal_states(self) -> None:
        loop = LookLoop()
        loop.create_request(
            tool_call_id="tool-6",
            reason="Request that fails",
            requested_at_ms=6_000,
        )
        loop.create_request(
            tool_call_id="tool-7",
            reason="Request that is cancelled",
            requested_at_ms=7_000,
        )

        failed = loop.fail_request("tool-6", "camera unavailable")
        cancelled = loop.cancel_request("tool-7")

        self.assertEqual(failed.state, LookLoopState.FAILED)
        self.assertEqual(failed.failure_reason, "camera unavailable")
        self.assertEqual(cancelled.state, LookLoopState.CANCELLED)
        self.assertEqual(cancelled.failure_reason, "look request cancelled")


if __name__ == "__main__":
    unittest.main()
