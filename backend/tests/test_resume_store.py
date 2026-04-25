from __future__ import annotations

import unittest

from app.session.resume_store import (
    DEFAULT_RESUME_TTL_SECONDS,
    InMemoryResumeStore,
    RestoreOutcome,
    TurnStateSnapshot,
)


class ResumeStoreTests(unittest.TestCase):
    def test_restore_returns_latest_snapshot_for_known_token(self) -> None:
        clock = _Clock()
        store = InMemoryResumeStore(clock=clock.now)

        created = store.upsert_session(
            "session-1",
            "resume-1",
            turn_state=TurnStateSnapshot(phase="ready", turn_id="turn-1"),
            resumable=True,
        )

        restored = store.restore("resume-1")

        self.assertEqual(restored.outcome, RestoreOutcome.RESTORED)
        self.assertIsNotNone(restored.session)
        assert restored.session is not None
        self.assertEqual(restored.session.session_id, "session-1")
        self.assertEqual(restored.session.resume_token, "resume-1")
        self.assertEqual(restored.session.turn_state, TurnStateSnapshot(phase="ready", turn_id="turn-1"))
        self.assertEqual(restored.session.known_resume_tokens, ("resume-1",))
        self.assertEqual(created, restored.session)

    def test_rotated_tokens_remain_valid_aliases_but_restore_prefers_latest_token(self) -> None:
        clock = _Clock()
        store = InMemoryResumeStore(clock=clock.now)
        store.upsert_session("session-1", "resume-1", resumable=True)

        clock.advance(5)
        store.upsert_session(
            "session-1",
            "resume-2",
            turn_state=TurnStateSnapshot(phase="ready", turn_id="turn-2"),
            resumable=True,
        )

        restored = store.restore("resume-1")

        self.assertEqual(restored.outcome, RestoreOutcome.RESTORED)
        assert restored.session is not None
        self.assertEqual(restored.matched_resume_token, "resume-1")
        self.assertEqual(restored.session.resume_token, "resume-2")
        self.assertEqual(restored.session.known_resume_tokens, ("resume-1", "resume-2"))
        self.assertEqual(restored.session.turn_state.turn_id, "turn-2")

    def test_store_blocks_restore_when_last_known_state_is_not_safe(self) -> None:
        store = InMemoryResumeStore(clock=_Clock().now)
        store.upsert_session(
            "session-1",
            "resume-1",
            turn_state=TurnStateSnapshot(
                phase="model_responding",
                turn_id="turn-7",
                response_id="resp-1",
                last_client_message_type="audio_end",
                last_server_event_type="audio_chunk",
            ),
            resumable=False,
        )

        restored = store.restore("resume-1")

        self.assertEqual(restored.outcome, RestoreOutcome.NOT_RESUMABLE)
        self.assertIsNone(restored.session)

        record = store.get("session-1")
        assert record is not None
        self.assertFalse(record.resumable)
        self.assertEqual(record.turn_state.phase, "model_responding")
        self.assertEqual(record.turn_state.response_id, "resp-1")

    def test_disconnected_sessions_expire_and_drop_all_token_aliases(self) -> None:
        clock = _Clock()
        store = InMemoryResumeStore(clock=clock.now, resume_ttl_seconds=30)
        store.upsert_session("session-1", "resume-1", resumable=True)
        store.upsert_session("session-1", "resume-2", resumable=True)
        store.mark_disconnected("session-1")

        clock.advance(29)
        self.assertEqual(store.expire_sessions(), ())
        self.assertEqual(store.restore("resume-1").outcome, RestoreOutcome.RESTORED)

        clock.advance(2)
        self.assertEqual(store.expire_sessions(), ("session-1",))
        self.assertEqual(store.restore("resume-1").outcome, RestoreOutcome.EXPIRED)
        self.assertEqual(store.restore("resume-2").outcome, RestoreOutcome.EXPIRED)
        self.assertIsNone(store.get("session-1"))

    def test_reconnecting_session_clears_disconnect_expiry(self) -> None:
        clock = _Clock()
        store = InMemoryResumeStore(clock=clock.now, resume_ttl_seconds=DEFAULT_RESUME_TTL_SECONDS)
        store.upsert_session("session-1", "resume-1", resumable=True)
        store.mark_disconnected("session-1")

        clock.advance(60)
        store.upsert_session(
            "session-1",
            "resume-2",
            turn_state=TurnStateSnapshot(phase="ready", turn_id="turn-9"),
            resumable=True,
        )
        clock.advance(DEFAULT_RESUME_TTL_SECONDS + 1)

        self.assertEqual(store.expire_sessions(), ())
        restored = store.restore("resume-2")
        self.assertEqual(restored.outcome, RestoreOutcome.RESTORED)
        assert restored.session is not None
        self.assertIsNone(restored.session.expires_at)


class _Clock:
    def __init__(self) -> None:
        self._value = 10_000.0

    def now(self) -> float:
        return self._value

    def advance(self, seconds: float) -> None:
        self._value += seconds


if __name__ == "__main__":
    unittest.main()
