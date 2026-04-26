from __future__ import annotations

import sys
import unittest
from pathlib import Path
from requests import HTTPError
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.task_scheduling_agent import create_calendar_event  # noqa: E402


class _FakeResponse:
    def __init__(self, payload: dict[str, object], *, status_error: HTTPError | None = None, text: str = "") -> None:
        self._payload = payload
        self._status_error = status_error
        self.text = text

    def raise_for_status(self) -> None:
        if self._status_error is not None:
            raise self._status_error
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class TaskSchedulingAgentCalendarTests(unittest.TestCase):
    @patch.dict(
        "os.environ",
        {
            "GCAL_CLIENT_ID": "client-id",
            "GCAL_CLIENT_SECRET": "client-secret",
            "GCAL_REFRESH_TOKEN": "refresh-token",
            "GCAL_CALENDAR_ID": "primary",
        },
        clear=False,
    )
    @patch("agents.task_scheduling_agent.requests.post")
    def test_create_calendar_event_refreshes_token_and_posts_event(self, mocked_post) -> None:
        mocked_post.side_effect = [
            _FakeResponse({"access_token": "access-token"}),
            _FakeResponse({"id": "calendar-event-id-123"}),
        ]

        event_result = create_calendar_event(
            summary="Design review",
            start_iso="2026-04-27T10:00:00Z",
            end_iso="2026-04-27T10:30:00Z",
            description="Review the latest mocks",
        )

        self.assertEqual(event_result["event_id"], "calendar-event-id-123")
        self.assertEqual(event_result["calendar_id"], "primary")
        self.assertEqual(event_result["calendar_tz"], "UTC")
        self.assertEqual(mocked_post.call_count, 2)
        self.assertIn("oauth2.googleapis.com/token", mocked_post.call_args_list[0].args[0])
        self.assertIn(
            "googleapis.com/calendar/v3/calendars/primary/events",
            mocked_post.call_args_list[1].args[0],
        )
        event_payload = mocked_post.call_args_list[1].kwargs["json"]
        self.assertEqual(event_payload["start"]["dateTime"], "2026-04-27T10:00:00Z")
        self.assertEqual(event_payload["start"]["timeZone"], "UTC")
        self.assertEqual(event_payload["end"]["timeZone"], "UTC")

    @patch.dict(
        "os.environ",
        {
            "GCAL_CLIENT_ID": "client-id",
            "GCAL_CLIENT_SECRET": "client-secret",
            "GCAL_REFRESH_TOKEN": "refresh-token",
            "GCAL_CALENDAR_ID": "primary",
        },
        clear=False,
    )
    @patch("agents.task_scheduling_agent.requests.post")
    def test_create_calendar_event_adds_timezone_to_naive_timestamps(self, mocked_post) -> None:
        mocked_post.side_effect = [
            _FakeResponse({"access_token": "access-token"}),
            _FakeResponse({"id": "calendar-event-id-123"}),
        ]

        event_result = create_calendar_event(
            summary="Design review",
            start_iso="2026-04-27T10:00:00",
            end_iso="2026-04-27T10:30:00",
            description="Review the latest mocks",
        )

        self.assertEqual(event_result["calendar_tz"], "UTC")
        event_payload = mocked_post.call_args_list[1].kwargs["json"]
        self.assertEqual(event_payload["start"]["dateTime"], "2026-04-27T10:00:00")
        self.assertEqual(event_payload["start"]["timeZone"], "UTC")
        self.assertEqual(event_payload["end"]["dateTime"], "2026-04-27T10:30:00")
        self.assertEqual(event_payload["end"]["timeZone"], "UTC")

    @patch.dict(
        "os.environ",
        {
            "GCAL_CLIENT_ID": "client-id",
            "GCAL_CLIENT_SECRET": "client-secret",
            "GCAL_REFRESH_TOKEN": "refresh-token",
            "GCAL_CALENDAR_ID": "primary",
        },
        clear=False,
    )
    @patch("agents.task_scheduling_agent.requests.post")
    def test_create_calendar_event_surfaces_google_error_details(self, mocked_post) -> None:
        event_error = HTTPError("403 Client Error: Forbidden for url")
        failing_event_response = _FakeResponse(
            {},
            status_error=event_error,
            text='{"error":{"code":403,"message":"Request had insufficient authentication scopes."}}',
        )
        event_error.response = failing_event_response
        mocked_post.side_effect = [
            _FakeResponse({"access_token": "access-token"}),
            failing_event_response,
        ]

        with self.assertRaisesRegex(RuntimeError, "insufficient authentication scopes"):
            create_calendar_event(
                summary="Design review",
                start_iso="2026-04-27T10:00:00Z",
                end_iso="2026-04-27T10:30:00Z",
                description="Review the latest mocks",
            )


if __name__ == "__main__":
    unittest.main()
