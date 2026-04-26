from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from ..google.models import LinkedGoogleUser
from ..google.oauth import GoogleOAuthSettings, get_google_oauth_service
from ..google.store import google_state_store


router = APIRouter(prefix="/google", tags=["google"])
logger = logging.getLogger(__name__)


def get_edith_dashboard_url(status: str = "connected") -> str:
    base_url = GoogleOAuthSettings().edith_app_url.rstrip("/")
    return f"{base_url}/dashboard?google={status}"


@router.get("/status")
def google_status() -> dict[str, object]:
    active_user = google_state_store.get_active_user()
    return {
        "connected": active_user is not None,
        "active_user": active_user.public_dict() if active_user is not None else None,
    }


@router.get("/history")
def google_history() -> dict[str, object]:
    return {
        "events": [event.model_dump() for event in google_state_store.get_history()],
    }


@router.post("/disconnect")
def google_disconnect() -> dict[str, object]:
    google_state_store.clear_active_user()
    return {
        "disconnected": True,
        "active_user": None,
    }


@router.get("/connect/start")
def google_connect_start() -> RedirectResponse:
    service = get_google_oauth_service()
    if service is None:
        raise HTTPException(status_code=503, detail="google_oauth_not_configured")
    return RedirectResponse(url=service.get_authorization_url())


@router.get("/connect/callback")
def google_connect_callback(code: str, state: str) -> RedirectResponse:
    service = get_google_oauth_service()
    if service is None:
        raise HTTPException(status_code=503, detail="google_oauth_not_configured")
    try:
        linked_user = LinkedGoogleUser.model_validate(service.exchange_code(code, state))
    except Exception:
        logger.exception("google_oauth_callback_failed")
        return RedirectResponse(url=get_edith_dashboard_url("error"))
    google_state_store.set_active_user(linked_user)
    return RedirectResponse(url=get_edith_dashboard_url("connected"))
