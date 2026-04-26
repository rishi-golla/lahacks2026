from __future__ import annotations

from fastapi.testclient import TestClient

from app.google.store import google_state_store
from app.main import app


client = TestClient(app)


def setup_function() -> None:
    google_state_store.reset()


def test_google_connect_start_returns_setup_error_when_oauth_not_configured() -> None:
    response = client.get("/google/connect/start")

    assert response.status_code == 503
    assert response.json()["detail"] == "google_oauth_not_configured"


def test_google_connect_start_redirects_to_google_auth_url_when_configured(monkeypatch) -> None:
    class FakeOAuthService:
        def get_authorization_url(self) -> str:
            return "https://accounts.google.com/o/oauth2/auth?fake=1"

    monkeypatch.setattr(
        "app.routers.google.get_google_oauth_service",
        lambda: FakeOAuthService(),
    )

    response = client.get("/google/connect/start", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "https://accounts.google.com/o/oauth2/auth?fake=1"


def test_google_connect_callback_stores_linked_user_identity(monkeypatch) -> None:
    class FakeOAuthService:
        def exchange_code(self, code: str) -> dict[str, object]:
            assert code == "test-code"
            return {
                "display_name": "Rishi Golla",
                "email": "rishi@example.com",
                "google_subject": "google-subject-1",
                "granted_scopes": [
                    "https://www.googleapis.com/auth/gmail.send",
                    "https://www.googleapis.com/auth/calendar.events",
                ],
                "connected_at": "2026-04-25T21:30:00Z",
                "status": "connected",
                "refresh_token": "refresh-token",
                "access_token": "access-token",
            }

    monkeypatch.setattr(
        "app.routers.google.get_google_oauth_service",
        lambda: FakeOAuthService(),
    )

    response = client.get("/google/connect/callback?code=test-code")

    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["active_user"]["email"] == "rishi@example.com"
    assert google_state_store.get_active_user() is not None
    assert google_state_store.get_active_user().email == "rishi@example.com"
