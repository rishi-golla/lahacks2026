from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_google_status_returns_disconnected_state_by_default() -> None:
    response = client.get("/google/status")

    assert response.status_code == 200
    assert response.json() == {
        "connected": False,
        "active_user": None,
    }


def test_google_history_returns_empty_list_by_default() -> None:
    response = client.get("/google/history")

    assert response.status_code == 200
    assert response.json() == {"events": []}


def test_google_disconnect_clears_linked_user_state() -> None:
    response = client.post("/google/disconnect")

    assert response.status_code == 200
    assert response.json() == {
        "disconnected": True,
        "active_user": None,
    }
