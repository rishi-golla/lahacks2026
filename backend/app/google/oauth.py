from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import os


GOOGLE_SCOPES = (
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/tasks",
)


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str


class GoogleOAuthService:
    def __init__(self, config: GoogleOAuthConfig) -> None:
        self._config = config

    def get_authorization_url(self) -> str:
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
        )
        flow.redirect_uri = self._config.redirect_uri
        auth_url, _state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return auth_url

    def exchange_code(self, code: str) -> dict[str, object]:
        from google.oauth2 import id_token
        from google.auth.transport.requests import Request
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
        )
        flow.redirect_uri = self._config.redirect_uri
        flow.fetch_token(code=code)
        credentials = flow.credentials
        token_info = id_token.verify_oauth2_token(
            credentials.id_token,
            Request(),
            self._config.client_id,
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
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    redirect_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")
    if not client_id or not client_secret or not redirect_uri:
        return None
    return GoogleOAuthService(
        GoogleOAuthConfig(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
    )
