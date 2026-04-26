from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from .confirmation import is_confirmation_yes
from .models import HistoryEvent, PendingGoogleAction
from .store import google_state_store


PROTECTED_GOOGLE_INTENTS = {"gmail", "google_calendar", "google_tasks"}


def begin_protected_action(intent: str, args: dict[str, str]) -> dict[str, str]:
    active_user = google_state_store.get_active_user()
    timestamp = _timestamp()
    if active_user is None:
        summary = "Google actions are not available yet. Please connect your Google account on the site first."
        google_state_store.append_history(
            HistoryEvent(
                id=_new_id("history"),
                timestamp=timestamp,
                intent=intent,
                actor_email=None,
                status="blocked",
                summary=summary,
                details={k: str(v) for k, v in args.items()},
            )
        )
        return {"status": "blocked", "summary": summary}

    prompt_text = f"Before I continue, just to confirm, are you {active_user.display_name}?"
    pending_action = PendingGoogleAction(
        id=_new_id("pending"),
        intent=intent,
        user_display_name=active_user.display_name,
        user_email=active_user.email,
        args={k: str(v) for k, v in args.items()},
        prompt_text=prompt_text,
        created_at=timestamp,
        expires_at=(datetime.now(UTC) + timedelta(minutes=2)).isoformat(),
    )
    google_state_store.set_pending_action(pending_action)
    google_state_store.append_history(
        HistoryEvent(
            id=_new_id("history"),
            timestamp=timestamp,
            intent=intent,
            actor_email=active_user.email,
            status="awaiting_confirmation",
            summary=prompt_text,
            details=pending_action.args,
        )
    )
    return {"status": "awaiting_confirmation", "summary": prompt_text}


def confirm_pending_action(text: str) -> dict[str, str] | None:
    pending_action = google_state_store.get_pending_action()
    if pending_action is None:
        return None

    google_state_store.clear_pending_action()
    if not is_confirmation_yes(text):
        summary = "Okay, I cancelled that Google action."
        google_state_store.append_history(
            HistoryEvent(
                id=_new_id("history"),
                timestamp=_timestamp(),
                intent=pending_action.intent,
                actor_email=pending_action.user_email,
                status="cancelled",
                summary=summary,
                details=pending_action.args,
            )
        )
        return {"status": "cancelled", "summary": summary}

    summary = _execute_stubbed_google_action(pending_action.intent, pending_action.args)
    google_state_store.append_history(
        HistoryEvent(
            id=_new_id("history"),
            timestamp=_timestamp(),
            intent=pending_action.intent,
            actor_email=pending_action.user_email,
            status="completed",
            summary=summary,
            details=pending_action.args,
        )
    )
    return {"status": "completed", "summary": summary}


def _execute_stubbed_google_action(intent: str, args: dict[str, str]) -> str:
    if intent == "gmail":
        recipient = args.get("recipient", "the requested recipient")
        return f"Confirmed. I completed the Gmail action for {recipient}."
    if intent == "google_calendar":
        details = args.get("details", "your calendar request")
        return f"Confirmed. I completed the Google Calendar action for {details}."
    if intent == "google_tasks":
        title = args.get("title", "your task")
        return f"Confirmed. I completed the Google Tasks action for {title}."
    return "Confirmed. I completed the requested Google action."


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"
