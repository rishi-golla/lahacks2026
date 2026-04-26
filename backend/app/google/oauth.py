from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..session.settings import BACKEND_ROOT

GOOGLE_SCOPES = (
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/tasks",
)
GOOGLE_OAUTH_CLOCK_SKEW_SECONDS = 600


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str


class GoogleOAuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    google_oauth_client_id: str | None = Field(default=None, alias="GOOGLE_OAUTH_CLIENT_ID")
    google_oauth_client_secret: str | None = Field(default=None, alias="GOOGLE_OAUTH_CLIENT_SECRET")
    google_oauth_redirect_uri: str | None = Field(default=None, alias="GOOGLE_OAUTH_REDIRECT_URI")
    edith_app_url: str = Field(default="http://127.0.0.1:5173", alias="EDITH_APP_URL")


_OAUTH_STATE_CODE_VERIFIERS: dict[str, str] = {}
_OAUTH_STATE_LOCK = Lock()


class GoogleOAuthService:
    def __init__(self, config: GoogleOAuthConfig) -> None:
        self._config = config

    def _build_flow(self, *, code_verifier: str | None = None):
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self._config.client_id,
                    "client_secret": self._config.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self._config.redirect_uri],
                }
            },
            scopes=list(GOOGLE_SCOPES),
            code_verifier=code_verifier,
        )
        flow.redirect_uri = self._config.redirect_uri
        return flow

    def get_authorization_url(self) -> str:
        flow = self._build_flow()
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        if flow.code_verifier is not None:
            with _OAUTH_STATE_LOCK:
                _OAUTH_STATE_CODE_VERIFIERS[state] = flow.code_verifier
        return auth_url

    def exchange_code(self, code: str, state: str) -> dict[str, object]:
        from google.oauth2 import id_token
        from google.auth.transport.requests import Request

        with _OAUTH_STATE_LOCK:
            code_verifier = _OAUTH_STATE_CODE_VERIFIERS.pop(state, None)
        if code_verifier is None:
            raise ValueError("missing_oauth_code_verifier")

        flow = self._build_flow(code_verifier=code_verifier)
        flow.fetch_token(code=code)
        credentials = flow.credentials
        token_info = id_token.verify_oauth2_token(
            credentials.id_token,
            Request(),
            self._config.client_id,
            clock_skew_in_seconds=GOOGLE_OAUTH_CLOCK_SKEW_SECONDS,
        )
        return {
            "display_name": str(token_info.get("name", token_info.get("email", "Google User"))),
            "email": str(token_info["email"]),
            "google_subject": str(token_info["sub"]),
            "granted_scopes": list(credentials.scopes or []),
            "connected_at": datetime.now(UTC).isoformat(),
            "status": "connected",
            "refresh_token": credentials.refresh_token,
            "access_token": credentials.token,
        }


def get_google_oauth_service() -> GoogleOAuthService | None:
    settings = GoogleOAuthSettings()
    client_id = settings.google_oauth_client_id
    client_secret = settings.google_oauth_client_secret
    redirect_uri = settings.google_oauth_redirect_uri
    if not client_id or not client_secret or not redirect_uri:
        return None
    return GoogleOAuthService(
        GoogleOAuthConfig(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
    )
