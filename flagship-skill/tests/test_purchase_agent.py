from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from browserbase_purchase import (  # noqa: E402
    STAGEHAND_BROWSER,
    StagehandSession,
    choose_candidate,
    ensure_price_allowed,
    score_candidate,
    _create_stagehand_session,
)
from browserbase_worker import app  # noqa: E402
from models import ProductCandidate, PurchaseItemQuery, parse_purchase_query  # noqa: E402


def test_parse_purchase_query_accepts_json_payload() -> None:
    query = parse_purchase_query(
        '{"description":"USB-C cable","quantity":2,"brand":"Anker","max_price":20}'
    )

    assert query.description == "USB-C cable"
    assert query.quantity == 2
    assert query.brand == "Anker"
    assert query.max_price == 20


def test_parse_purchase_query_accepts_natural_language_guards() -> None:
    query = parse_purchase_query("Buy a 6ft USB-C cable qty 2 under $15")

    assert query.description == "Buy a 6ft USB-C cable qty 2 under $15"
    assert query.quantity == 2
    assert query.max_price == 15


def test_score_candidate_rewards_matching_metadata() -> None:
    query = PurchaseItemQuery(description="USB-C charging cable 6ft", brand="Anker")
    good = ProductCandidate(title="Anker USB-C Charging Cable 6ft Braided", price=9.99)
    bad = ProductCandidate(title="Wireless mouse with USB receiver", price=9.99)

    assert score_candidate(query, good) > score_candidate(query, bad)


def test_choose_candidate_returns_ambiguous_for_close_scores() -> None:
    query = PurchaseItemQuery(description="USB-C cable 6ft")
    candidates = [
        ProductCandidate(title="USB-C cable 6ft black", price=8.99),
        ProductCandidate(title="USB-C cable 6ft white", price=8.99),
    ]

    decision, selected = choose_candidate(query, candidates)

    assert decision == "ambiguous"
    assert selected is not None


def test_price_guard_blocks_total_above_max() -> None:
    query = PurchaseItemQuery(description="USB-C cable", quantity=2, max_price=10)

    try:
        ensure_price_allowed(query, 6)
    except ValueError as exc:
        assert "exceeds max_price" in str(exc)
    else:
        raise AssertionError("expected price guard to raise")


def test_stagehand_session_wrapper_calls_sdk_with_session_id() -> None:
    sessions = _FakeStagehandSessions()
    session = StagehandSession(client=SimpleNamespace(sessions=sessions), id="session-123")

    async def run() -> None:
        await session.navigate(url="https://www.amazon.com")
        await session.extract(instruction="extract page", schema={"type": "object"})
        await session.act(input="click cart")
        await session.end()

    asyncio.run(run())

    assert sessions.calls == [
        ("navigate", "session-123", {"url": "https://www.amazon.com"}),
        ("extract", "session-123", {"instruction": "extract page", "schema": {"type": "object"}}),
        ("act", "session-123", {"input": "click cart"}),
        ("end", "session-123", {}),
    ]


def test_stagehand_session_create_omits_paid_browserbase_features_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BROWSERBASE_PROJECT_ID", "project-123")
    monkeypatch.setenv("BROWSERBASE_CONTEXT_ID", "context-123")
    monkeypatch.delenv("BROWSERBASE_USE_PROXY", raising=False)
    monkeypatch.delenv("BROWSERBASE_PROXY_CITY", raising=False)
    monkeypatch.delenv("BROWSERBASE_PROXY_STATE", raising=False)
    monkeypatch.delenv("BROWSERBASE_PROXY_COUNTRY", raising=False)
    sessions = _FakeStagehandStartSessions()

    asyncio.run(_create_stagehand_session(SimpleNamespace(sessions=sessions)))

    assert sessions.start_kwargs["model_name"] == "google/gemini-3-flash-preview"
    params = sessions.start_kwargs["browserbase_session_create_params"]
    assert sessions.start_kwargs["browser"] == STAGEHAND_BROWSER
    assert sessions.start_kwargs["browser"]["launch_options"]["headless"] is False
    assert "proxies" not in params
    assert "solve_captchas" not in params["browser_settings"]
    assert "wait_for_captcha_solves" not in sessions.start_kwargs


def test_stagehand_session_create_includes_proxy_only_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BROWSERBASE_PROJECT_ID", "project-123")
    monkeypatch.setenv("BROWSERBASE_CONTEXT_ID", "context-123")
    monkeypatch.setenv("BROWSERBASE_USE_PROXY", "1")
    monkeypatch.setenv("BROWSERBASE_PROXY_CITY", "New York")
    monkeypatch.setenv("BROWSERBASE_PROXY_STATE", "NY")
    monkeypatch.setenv("BROWSERBASE_PROXY_COUNTRY", "US")
    sessions = _FakeStagehandStartSessions()

    asyncio.run(_create_stagehand_session(SimpleNamespace(sessions=sessions)))

    params = sessions.start_kwargs["browserbase_session_create_params"]
    assert params["proxies"] == [
        {
            "type": "browserbase",
            "geolocation": {"city": "New York", "state": "NY", "country": "US"},
        }
    ]


@pytest.mark.integration
def test_purchase_agent_payload_uses_actual_local_stagehand_worker() -> None:
    _load_dotenv()
    _skip_unless_live_stagehand()

    client = TestClient(app)
    response = client.post(
        "/v1/purchase/review",
        json=PurchaseItemQuery(
            description=os.environ.get("LIVE_PURCHASE_DESCRIPTION", "USB-C charging cable 6ft"),
            quantity=int(os.environ.get("LIVE_PURCHASE_QUANTITY", "1")),
            max_price=float(os.environ.get("LIVE_PURCHASE_MAX_PRICE", "15")),
        ).model_dump(exclude_none=True),
    )

    assert response.status_code == 200
    payload = response.json()
    print(payload)
    assert payload["status"] in {"review_ready", "needs_auth", "not_found", "ambiguous", "blocked"}
    assert not payload.get("error"), payload
    assert payload["requires_confirmation"] is True
    assert payload.get("browserbase_session_id"), payload
    assert payload.get("recording_url"), payload


def _skip_unless_live_stagehand() -> None:
    if os.environ.get("LIVE_BROWSERBASE") != "1":
        pytest.skip("set LIVE_BROWSERBASE=1 to run actual local Stagehand/Browserbase integration")

    missing = [
        name
        for name in ("BROWSERBASE_API_KEY", "BROWSERBASE_PROJECT_ID", "BROWSERBASE_CONTEXT_ID", "MODEL_API_KEY")
        if not os.environ.get(name)
    ]
    if missing:
        pytest.skip(f"missing Stagehand/Browserbase env vars: {', '.join(missing)}")


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


class _FakeStagehandSessions:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    async def navigate(self, session_id: str, **kwargs):
        self.calls.append(("navigate", session_id, kwargs))

    async def extract(self, session_id: str, **kwargs):
        self.calls.append(("extract", session_id, kwargs))

    async def act(self, session_id: str, **kwargs):
        self.calls.append(("act", session_id, kwargs))

    async def end(self, session_id: str, **kwargs):
        self.calls.append(("end", session_id, kwargs))


class _FakeStagehandStartSessions:
    def __init__(self) -> None:
        self.start_kwargs: dict = {}

    async def start(self, **kwargs):
        self.start_kwargs = kwargs
        return {"data": {"sessionId": "session-123"}}
