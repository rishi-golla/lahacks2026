from __future__ import annotations

from app.google.actions import (
    begin_protected_action,
    confirm_pending_action,
)
from app.google.models import LinkedGoogleUser
from app.google.store import google_state_store


def setup_function() -> None:
    google_state_store.reset()


def test_protected_action_without_linked_user_is_refused() -> None:
    result = begin_protected_action("gmail", {"recipient": "sarah@example.com"})

    assert result["status"] == "blocked"
    assert "connect" in result["summary"].lower()
    assert google_state_store.get_pending_action() is None
    assert google_state_store.get_history()[-1].status == "blocked"


def test_protected_action_with_linked_user_creates_pending_confirmation() -> None:
    google_state_store.set_active_user(
        LinkedGoogleUser(
            display_name="Rishi Golla",
            email="rishi@example.com",
            google_subject="google-subject-1",
            granted_scopes=["https://www.googleapis.com/auth/gmail.send"],
            connected_at="2026-04-25T21:30:00Z",
        )
    )

    result = begin_protected_action("gmail", {"recipient": "sarah@example.com"})

    assert result["status"] == "awaiting_confirmation"
    assert "are you rishi golla" in result["summary"].lower()
    pending = google_state_store.get_pending_action()
    assert pending is not None
    assert pending.intent == "gmail"


def test_yes_confirms_and_executes_pending_action() -> None:
    google_state_store.set_active_user(
        LinkedGoogleUser(
            display_name="Rishi Golla",
            email="rishi@example.com",
            google_subject="google-subject-1",
            granted_scopes=["https://www.googleapis.com/auth/gmail.send"],
            connected_at="2026-04-25T21:30:00Z",
        )
    )
    begin_protected_action("gmail", {"recipient": "sarah@example.com"})

    result = confirm_pending_action("yes")

    assert result is not None
    assert result["status"] == "completed"
    assert "gmail" in result["summary"].lower()
    assert google_state_store.get_pending_action() is None
    assert google_state_store.get_history()[-1].status == "completed"


def test_non_yes_cancels_pending_action() -> None:
    google_state_store.set_active_user(
        LinkedGoogleUser(
            display_name="Rishi Golla",
            email="rishi@example.com",
            google_subject="google-subject-1",
            granted_scopes=["https://www.googleapis.com/auth/gmail.send"],
            connected_at="2026-04-25T21:30:00Z",
        )
    )
    begin_protected_action("gmail", {"recipient": "sarah@example.com"})

    result = confirm_pending_action("no")

    assert result is not None
    assert result["status"] == "cancelled"
    assert "cancelled" in result["summary"].lower()
    assert google_state_store.get_pending_action() is None
    assert google_state_store.get_history()[-1].status == "cancelled"
