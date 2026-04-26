from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from browserbase_worker import app  # noqa: E402
from models import PurchaseStatus  # noqa: E402


_LIVE_STATUSES: set[PurchaseStatus] = {
    "review_ready",
    "needs_auth",
    "not_found",
    "ambiguous",
    "blocked",
}


def test_health_endpoint_is_real_worker_app() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
def test_purchase_worker_live_browserbase_review_flow() -> None:
    _load_dotenv()
    _skip_unless_live_browserbase()

    client = TestClient(app)
    response = client.post(
        "/v1/purchase/review",
        json={
            "description": os.environ.get("LIVE_PURCHASE_DESCRIPTION", "USB-C charging cable 6ft"),
            "quantity": int(os.environ.get("LIVE_PURCHASE_QUANTITY", "1")),
            "max_price": float(os.environ.get("LIVE_PURCHASE_MAX_PRICE", "15")),
        },
        timeout=180,
    )

    assert response.status_code == 200
    payload = response.json()
    print(payload)
    assert payload["status"] in _LIVE_STATUSES
    assert not payload.get("error"), payload
    assert payload["requires_confirmation"] is True
    assert payload.get("browserbase_session_id"), payload
    assert payload.get("recording_url"), payload
    assert "place order" not in payload.get("summary", "").lower()


def _skip_unless_live_browserbase() -> None:
    if os.environ.get("LIVE_BROWSERBASE") != "1":
        pytest.skip("set LIVE_BROWSERBASE=1 to run real Browserbase/Amazon integration")

    missing = [
        name
        for name in ("BROWSERBASE_API_KEY", "BROWSERBASE_PROJECT_ID", "BROWSERBASE_CONTEXT_ID", "MODEL_API_KEY")
        if not os.environ.get(name)
    ]
    if missing:
        pytest.skip(f"missing Browserbase env vars: {', '.join(missing)}")


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())
