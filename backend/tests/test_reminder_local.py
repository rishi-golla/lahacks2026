"""Unit tests for backend in-session reminder nudges."""

from __future__ import annotations

import unittest

from app.reminder_local import parse_delay_seconds, schedule_local_reminder_if_imminent


class ReminderLocalParseTests(unittest.TestCase):
    def test_parses_in_n_seconds(self) -> None:
        self.assertEqual(parse_delay_seconds("Remind me in 10 seconds to stretch"), 10.0)
        self.assertEqual(parse_delay_seconds("in 3 seconds"), 3.0)

    def test_parses_in_minutes(self) -> None:
        self.assertEqual(parse_delay_seconds("in 2 minutes to drink water"), 120.0)

    def test_returns_none_when_no_time(self) -> None:
        self.assertIsNone(parse_delay_seconds("remind me tomorrow to call mom"))


class ReminderLocalScheduleNoopTests(unittest.TestCase):
    def test_does_not_schedule_for_non_reminder(self) -> None:
        # Should not raise; no asyncio task to await here.
        schedule_local_reminder_if_imminent(
            intent="send an email",
            args={},
            session_id="session-x",
            sender=object(),  # unused when not a reminder
        )
