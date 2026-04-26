from __future__ import annotations

from fastapi.testclient import TestClient

from app.google.oauth import GOOGLE_SCOPES, _OAUTH_STATE_CODE_VERIFIERS, get_google_oauth_service
from app.google.store import google_state_store
from app.main import app


client = TestClient(app)


def setup_function() -> None:
    google_state_store.reset()
    _OAUTH_STATE_CODE_VERIFIERS.clear()


def test_google_connect_start_returns_setup_error_when_oauth_not_configured() -> None:
    from app.routers import google as google_router

    original = google_router.get_google_oauth_service
    google_router.get_google_oauth_service = lambda: None
    try:
        response = client.get("/google/connect/start")
    finally:
        google_router.get_google_oauth_service = original

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


def test_google_oauth_service_uses_backend_settings_loader(monkeypatch) -> None:
    class FakeSettings:
        google_oauth_client_id = "client-id"
        google_oauth_client_secret = "client-secret"
        google_oauth_redirect_uri = "http://127.0.0.1:8000/google/connect/callback"

    monkeypatch.setattr("app.google.oauth.GoogleOAuthSettings", lambda: FakeSettings())

    service = get_google_oauth_service()

    assert service is not None
    assert service._config.client_id == "client-id"  # noqa: SLF001
    assert service._config.client_secret == "client-secret"  # noqa: SLF001
    assert (
        service._config.redirect_uri  # noqa: SLF001
        == "http://127.0.0.1:8000/google/connect/callback"
    )


def test_google_oauth_uses_canonical_userinfo_scopes() -> None:
    assert "openid" in GOOGLE_SCOPES
    assert "https://www.googleapis.com/auth/userinfo.email" in GOOGLE_SCOPES
    assert "https://www.googleapis.com/auth/userinfo.profile" in GOOGLE_SCOPES
    assert "email" not in GOOGLE_SCOPES
    assert "profile" not in GOOGLE_SCOPES


def test_google_oauth_verifies_id_token_with_clock_skew_allowance(monkeypatch) -> None:
    created_flows: list[FakeFlow] = []
    verify_calls: list[dict[str, object]] = []

    class FakeCredentials:
        id_token = "fake-id-token"
        scopes = ["https://www.googleapis.com/auth/gmail.send"]
        refresh_token = "refresh-token"
        token = "access-token"

    class FakeFlow:
        def __init__(self) -> None:
            self.redirect_uri: str | None = None
            self.code_verifier: str | None = None
            self.credentials = FakeCredentials()

        def authorization_url(self, **kwargs) -> tuple[str, str]:
            self.code_verifier = "pkce-verifier-123"
            return "https://accounts.google.com/o/oauth2/auth?fake=1", "oauth-state-123"

        def fetch_token(self, **kwargs) -> None:
            return None

    def fake_from_client_config(*_args, **kwargs) -> FakeFlow:
        flow = FakeFlow()
        flow.code_verifier = kwargs.get("code_verifier")
        created_flows.append(flow)
        return flow

    def fake_verify(id_token_value, request, audience, **kwargs):
        verify_calls.append(
            {
                "id_token": id_token_value,
                "audience": audience,
                "clock_skew_in_seconds": kwargs.get("clock_skew_in_seconds"),
            }
        )
        return {
            "name": "Rishi Golla",
            "email": "rishi@example.com",
            "sub": "google-subject-1",
        }

    monkeypatch.setattr(
        "google_auth_oauthlib.flow.Flow.from_client_config",
        fake_from_client_config,
    )
    monkeypatch.setattr("google.oauth2.id_token.verify_oauth2_token", fake_verify)

    service = get_google_oauth_service()
    assert service is not None

    service.get_authorization_url()
    payload = service.exchange_code("test-code", "oauth-state-123")

    assert payload["email"] == "rishi@example.com"
    assert created_flows[1].code_verifier == "pkce-verifier-123"
    assert verify_calls == [
        {
            "id_token": "fake-id-token",
            "audience": service._config.client_id,  # noqa: SLF001
            "clock_skew_in_seconds": 600,
        }
    ]


def test_google_connect_callback_stores_linked_user_identity(monkeypatch) -> None:
    class FakeOAuthService:
        def exchange_code(self, code: str, state: str) -> dict[str, object]:
            assert code == "test-code"
            assert state == "oauth-state-123"
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
    monkeypatch.setattr(
        "app.routers.google.get_edith_dashboard_url",
        lambda status="connected": f"http://127.0.0.1:5173/dashboard?google={status}",
    )

    response = client.get(
        "/google/connect/callback?code=test-code&state=oauth-state-123",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert (
        response.headers["location"]
        == "http://127.0.0.1:5173/dashboard?google=connected"
    )
    assert google_state_store.get_active_user() is not None
    assert google_state_store.get_active_user().email == "rishi@example.com"


def test_google_connect_callback_redirects_to_dashboard_with_error_when_exchange_fails(
    monkeypatch,
) -> None:
    class FakeOAuthService:
        def exchange_code(self, code: str, state: str) -> dict[str, object]:
            assert code == "bad-code"
            assert state == "oauth-state-123"
            raise RuntimeError("oauth_exchange_failed")

    monkeypatch.setattr(
        "app.routers.google.get_google_oauth_service",
        lambda: FakeOAuthService(),
    )
    monkeypatch.setattr(
        "app.routers.google.get_edith_dashboard_url",
        lambda status="connected": f"http://127.0.0.1:5173/dashboard?google={status}",
    )

    response = client.get(
        "/google/connect/callback?code=bad-code&state=oauth-state-123",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "http://127.0.0.1:5173/dashboard?google=error"
    assert google_state_store.get_active_user() is None


def test_google_oauth_service_reuses_code_verifier_for_callback(monkeypatch) -> None:
    created_flows: list[FakeFlow] = []

    class FakeCredentials:
        id_token = "fake-id-token"
        scopes = ["https://www.googleapis.com/auth/gmail.send"]
        refresh_token = "refresh-token"
        token = "access-token"

    class FakeFlow:
        def __init__(self) -> None:
            self.redirect_uri: str | None = None
            self.code_verifier: str | None = None
            self.credentials = FakeCredentials()
            self.fetch_token_calls: list[dict[str, str]] = []

        def authorization_url(self, **kwargs) -> tuple[str, str]:
            self.code_verifier = "pkce-verifier-123"
            return "https://accounts.google.com/o/oauth2/auth?fake=1", "oauth-state-123"

        def fetch_token(self, **kwargs) -> None:
            self.fetch_token_calls.append(kwargs)

    def fake_from_client_config(*_args, **kwargs) -> FakeFlow:
        flow = FakeFlow()
        flow.code_verifier = kwargs.get("code_verifier")
        created_flows.append(flow)
        return flow

    monkeypatch.setattr(
        "google_auth_oauthlib.flow.Flow.from_client_config",
        fake_from_client_config,
    )
    monkeypatch.setattr(
        "google.oauth2.id_token.verify_oauth2_token",
        lambda *_args, **_kwargs: {
            "name": "Rishi Golla",
            "email": "rishi@example.com",
            "sub": "google-subject-1",
        },
    )

    service = get_google_oauth_service()
    assert service is not None

    auth_url = service.get_authorization_url()
    assert auth_url == "https://accounts.google.com/o/oauth2/auth?fake=1"

    payload = service.exchange_code("test-code", "oauth-state-123")

    assert payload["email"] == "rishi@example.com"
    assert len(created_flows) == 2
    assert created_flows[1].code_verifier == "pkce-verifier-123"
    assert created_flows[1].fetch_token_calls == [{"code": "test-code"}]


def test_google_oauth_service_reuses_code_verifier_across_service_instances(monkeypatch) -> None:
    created_flows: list[FakeFlow] = []

    class FakeCredentials:
        id_token = "fake-id-token"
        scopes = ["https://www.googleapis.com/auth/gmail.send"]
        refresh_token = "refresh-token"
        token = "access-token"

    class FakeFlow:
        def __init__(self) -> None:
            self.redirect_uri: str | None = None
            self.code_verifier: str | None = None
            self.credentials = FakeCredentials()
            self.fetch_token_calls: list[dict[str, str]] = []

        def authorization_url(self, **kwargs) -> tuple[str, str]:
            self.code_verifier = "pkce-verifier-cross-request"
            return "https://accounts.google.com/o/oauth2/auth?fake=1", "oauth-state-cross-request"

        def fetch_token(self, **kwargs) -> None:
            self.fetch_token_calls.append(kwargs)

    def fake_from_client_config(*_args, **kwargs) -> FakeFlow:
        flow = FakeFlow()
        flow.code_verifier = kwargs.get("code_verifier")
        created_flows.append(flow)
        return flow

    monkeypatch.setattr(
        "google_auth_oauthlib.flow.Flow.from_client_config",
        fake_from_client_config,
    )
    monkeypatch.setattr(
        "google.oauth2.id_token.verify_oauth2_token",
        lambda *_args, **_kwargs: {
            "name": "Rishi Golla",
            "email": "rishi@example.com",
            "sub": "google-subject-1",
        },
    )

    first_service = get_google_oauth_service()
    second_service = get_google_oauth_service()

    assert first_service is not None
    assert second_service is not None
    assert first_service is not second_service

    auth_url = first_service.get_authorization_url()
    assert auth_url == "https://accounts.google.com/o/oauth2/auth?fake=1"

    payload = second_service.exchange_code("test-code", "oauth-state-cross-request")

    assert payload["email"] == "rishi@example.com"
    assert len(created_flows) == 2
    assert created_flows[1].code_verifier == "pkce-verifier-cross-request"
    assert created_flows[1].fetch_token_calls == [{"code": "test-code"}]
