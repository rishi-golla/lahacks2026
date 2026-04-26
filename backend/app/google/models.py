from __future__ import annotations

from pydantic import BaseModel


class LinkedGoogleUser(BaseModel):
    display_name: str
    email: str
    google_subject: str
    granted_scopes: list[str]
    connected_at: str
    status: str = "connected"
    refresh_token: str | None = None
    access_token: str | None = None

    def public_dict(self) -> dict[str, object]:
        return {
            "display_name": self.display_name,
            "email": self.email,
            "google_subject": self.google_subject,
            "granted_scopes": list(self.granted_scopes),
            "connected_at": self.connected_at,
            "status": self.status,
        }


class HistoryEvent(BaseModel):
    id: str
    timestamp: str
    intent: str
    actor_email: str | None = None
    status: str
    summary: str
    details: dict[str, str] | None = None


class PendingGoogleAction(BaseModel):
    id: str
    intent: str
    user_display_name: str
    user_email: str
    args: dict[str, str]
    prompt_text: str
    created_at: str
    expires_at: str
    status: str = "awaiting_confirmation"
