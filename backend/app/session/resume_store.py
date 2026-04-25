"""In-memory session resume token storage.

This module intentionally stays decoupled from the websocket coordinator so it
can be integrated incrementally. It tracks:

- stable session IDs
- one or more known resume tokens for a session
- the latest turn snapshot we know about
- whether the session is currently safe to resume
- disconnect-based expiry for stale state
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import threading
import time
from typing import Callable

DEFAULT_RESUME_TTL_SECONDS = 2 * 60 * 60


class RestoreOutcome(StrEnum):
    RESTORED = "restored"
    UNKNOWN = "unknown"
    NOT_RESUMABLE = "not_resumable"
    EXPIRED = "expired"


@dataclass(slots=True, frozen=True)
class TurnStateSnapshot:
    """Last known coordinator/model turn state for a session."""

    phase: str
    turn_id: str | None = None
    response_id: str | None = None
    last_client_message_type: str | None = None
    last_server_event_type: str | None = None


@dataclass(slots=True, frozen=True)
class ResumeSessionRecord:
    """Stored resumability state for one logical session."""

    session_id: str
    resume_token: str
    known_resume_tokens: tuple[str, ...]
    turn_state: TurnStateSnapshot
    resumable: bool
    created_at: float
    updated_at: float
    disconnected_at: float | None = None
    expires_at: float | None = None


@dataclass(slots=True, frozen=True)
class RestoreResult:
    """Result of looking up a token for session restoration."""

    outcome: RestoreOutcome
    matched_resume_token: str | None = None
    session: ResumeSessionRecord | None = None


class InMemoryResumeStore:
    """Simple in-memory resume store for reconnect-safe session state."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        resume_ttl_seconds: float = DEFAULT_RESUME_TTL_SECONDS,
    ) -> None:
        self._clock = clock or time.time
        self._resume_ttl_seconds = resume_ttl_seconds
        self._records_by_session_id: dict[str, ResumeSessionRecord] = {}
        self._session_id_by_token: dict[str, str] = {}
        self._expired_tokens: dict[str, float] = {}
        self._lock = threading.RLock()

    def upsert_session(
        self,
        session_id: str,
        resume_token: str,
        *,
        turn_state: TurnStateSnapshot | None = None,
        resumable: bool | None = None,
    ) -> ResumeSessionRecord:
        """Create or refresh a session record and attach the latest token."""

        with self._lock:
            now = self._clock()
            existing = self._records_by_session_id.get(session_id)
            baseline = existing or ResumeSessionRecord(
                session_id=session_id,
                resume_token=resume_token,
                known_resume_tokens=(resume_token,),
                turn_state=turn_state or TurnStateSnapshot(phase="unknown"),
                resumable=False if resumable is None else resumable,
                created_at=now,
                updated_at=now,
            )

            known_tokens = _append_unique(baseline.known_resume_tokens, resume_token)
            next_record = replace(
                baseline,
                resume_token=resume_token,
                known_resume_tokens=known_tokens,
                turn_state=turn_state or baseline.turn_state,
                resumable=baseline.resumable if resumable is None else resumable,
                updated_at=now,
                disconnected_at=None,
                expires_at=None,
            )
            self._records_by_session_id[session_id] = next_record

            for token in known_tokens:
                self._expired_tokens.pop(token, None)
                self._session_id_by_token[token] = session_id

            return next_record

    def get(self, session_id: str) -> ResumeSessionRecord | None:
        with self._lock:
            return self._records_by_session_id.get(session_id)

    def mark_turn_state(
        self,
        session_id: str,
        turn_state: TurnStateSnapshot,
        *,
        resumable: bool | None = None,
    ) -> ResumeSessionRecord:
        """Update the last known turn state for a stored session."""

        with self._lock:
            record = self._require_session(session_id)
            next_record = replace(
                record,
                turn_state=turn_state,
                resumable=record.resumable if resumable is None else resumable,
                updated_at=self._clock(),
            )
            self._records_by_session_id[session_id] = next_record
            return next_record

    def mark_disconnected(
        self,
        session_id: str,
        *,
        turn_state: TurnStateSnapshot | None = None,
        resumable: bool | None = None,
    ) -> ResumeSessionRecord:
        """Start the expiry window for a disconnected session."""

        with self._lock:
            record = self._require_session(session_id)
            now = self._clock()
            next_record = replace(
                record,
                turn_state=turn_state or record.turn_state,
                resumable=record.resumable if resumable is None else resumable,
                updated_at=now,
                disconnected_at=now,
                expires_at=now + self._resume_ttl_seconds,
            )
            self._records_by_session_id[session_id] = next_record
            return next_record

    def restore(self, resume_token: str) -> RestoreResult:
        """Resolve a resume token into the latest safe session snapshot."""

        with self._lock:
            self._expire_sessions_locked()

            session_id = self._session_id_by_token.get(resume_token)
            if session_id is None:
                if resume_token in self._expired_tokens:
                    return RestoreResult(
                        outcome=RestoreOutcome.EXPIRED,
                        matched_resume_token=resume_token,
                    )
                return RestoreResult(outcome=RestoreOutcome.UNKNOWN)

            record = self._records_by_session_id.get(session_id)
            if record is None:
                return RestoreResult(outcome=RestoreOutcome.UNKNOWN)
            if not record.resumable:
                return RestoreResult(
                    outcome=RestoreOutcome.NOT_RESUMABLE,
                    matched_resume_token=resume_token,
                )
            return RestoreResult(
                outcome=RestoreOutcome.RESTORED,
                matched_resume_token=resume_token,
                session=record,
            )

    def expire_sessions(self) -> tuple[str, ...]:
        """Drop disconnected sessions whose resume window has elapsed."""

        with self._lock:
            return self._expire_sessions_locked()

    def _expire_sessions_locked(self) -> tuple[str, ...]:
        now = self._clock()
        expired_session_ids: list[str] = []

        for session_id, record in tuple(self._records_by_session_id.items()):
            if record.expires_at is None or record.expires_at > now:
                continue

            expired_session_ids.append(session_id)
            self._records_by_session_id.pop(session_id, None)
            for token in record.known_resume_tokens:
                self._session_id_by_token.pop(token, None)
                self._expired_tokens[token] = now

        return tuple(expired_session_ids)

    def _require_session(self, session_id: str) -> ResumeSessionRecord:
        record = self._records_by_session_id.get(session_id)
        if record is None:
            raise KeyError(f"unknown session_id: {session_id}")
        return record


def _append_unique(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    if value in values:
        return values
    return (*values, value)
