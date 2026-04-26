"""Stagehand implementation for Amazon checkout review prep."""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

from models import ProductCandidate, PurchaseItemQuery, PurchaseItemResult


AMAZON_URL = os.environ.get("AMAZON_URL", "https://www.amazon.com")
DEFAULT_MAX_TOTAL = os.environ.get("PURCHASE_MAX_TOTAL_USD")
STAGEHAND_MODEL_NAME = os.environ.get("STAGEHAND_MODEL_NAME", "google/gemini-3-flash-preview")
STAGEHAND_BROWSER = {"type": "browserbase", "launch_options": {"headless": False}}
AMBIGUOUS_SCORE_DELTA = 0.08
MIN_ACCEPT_SCORE = 0.34


class StagehandConfigError(RuntimeError):
    pass


@dataclass(slots=True)
class BrowserSessionInfo:
    session_id: str
    recording_url: str


@dataclass(slots=True)
class StagehandSession:
    client: Any
    id: str

    async def navigate(self, *, url: str) -> Any:
        return await self.client.sessions.navigate(self.id, url=url)

    async def act(self, *, input: str | dict[str, Any]) -> Any:
        return await self.client.sessions.act(self.id, input=input)

    async def extract(self, *, instruction: str, schema: dict[str, Any]) -> Any:
        return await self.client.sessions.extract(self.id, instruction=instruction, schema=schema)

    async def end(self) -> Any:
        return await self.client.sessions.end(self.id)


async def prepare_purchase_review(query: PurchaseItemQuery) -> PurchaseItemResult:
    """Prepare an Amazon checkout review using Stagehand.

    The flow intentionally stops at review. It never asks Stagehand to click a
    final order/place-order button.
    """
    _validate_stagehand_env()
    session = None
    session_info: BrowserSessionInfo | None = None

    try:
        client = _create_stagehand_client()
        session = await _create_stagehand_session(client)
        session_info = _session_info(session)

        await session.navigate(url=f"{AMAZON_URL}/s?k={quote_plus(build_search_terms(query))}")
        page_state = await _extract_page_state(session)
        if _state_is_blocked(page_state):
            return _blocked_result(query, session_info)
        if _state_needs_auth(page_state):
            return _needs_auth_result(query, session_info)

        candidates = _candidates_from_page_state(page_state)
        decision, selected = choose_candidate(query, candidates)
        if decision == "ambiguous":
            return PurchaseItemResult(
                status="ambiguous",
                summary="I found multiple plausible Amazon matches and need a clearer product description.",
                confidence="medium",
                quantity=query.quantity,
                candidates=candidates[:5],
                browserbase_session_id=session_info.session_id,
                recording_url=session_info.recording_url,
            )
        if selected is None:
            return PurchaseItemResult(
                status="not_found",
                summary="I could not find a confident Amazon match for that product.",
                confidence="low",
                quantity=query.quantity,
                candidates=candidates[:5],
                browserbase_session_id=session_info.session_id,
                recording_url=session_info.recording_url,
            )

        ensure_price_allowed(query, selected.price)
        await session.act(input=_open_product_instruction(selected))
        product_state = await _extract_product_state(session)
        if _state_needs_auth(product_state):
            return _needs_auth_result(query, session_info)
        if _product_unavailable(product_state):
            return PurchaseItemResult(
                status="not_found",
                summary="The selected Amazon item appears to be unavailable.",
                confidence="low",
                product_title=selected.title,
                product_url=selected.url,
                price=selected.price_text or selected.price,
                quantity=query.quantity,
                browserbase_session_id=session_info.session_id,
                recording_url=session_info.recording_url,
            )

        await session.act(input=_set_quantity_instruction(query.quantity))
        await session.act(input="Add the current product to the cart. Do not buy now and do not place the order.")
        await session.act(
            input=(
                "Go to the Amazon checkout review page for the cart. "
                "Stop once the order can be reviewed. Do not click any button that places, submits, or completes the order."
            )
        )

        review_state = await _extract_review_state(session)
        if _state_needs_auth(review_state):
            return _needs_auth_result(query, session_info)
        if _state_is_blocked(review_state):
            return _blocked_result(query, session_info)

        title = _as_str(review_state.get("product_title")) or selected.title
        price = _as_str(review_state.get("price")) or selected.price_text or selected.price
        checkout_url = _as_str(review_state.get("current_url"))
        return PurchaseItemResult(
            status="review_ready",
            summary="Amazon checkout review is ready. The final order was not placed.",
            confidence="high",
            product_title=title,
            product_url=selected.url,
            price=price,
            quantity=query.quantity,
            checkout_url=checkout_url,
            browserbase_session_id=session_info.session_id,
            recording_url=session_info.recording_url,
        )
    except ValueError as exc:
        return PurchaseItemResult(status="blocked", summary=str(exc), confidence="low", quantity=query.quantity)
    except Exception as exc:  # noqa: BLE001
        return PurchaseItemResult(
            status="error",
            summary="Stagehand could not prepare the Amazon checkout review.",
            confidence="low",
            quantity=query.quantity,
            browserbase_session_id=session_info.session_id if session_info else None,
            recording_url=session_info.recording_url if session_info else None,
            error=str(exc),
        )
    finally:
        if session is not None:
            await _end_session(session)


def build_search_terms(query: PurchaseItemQuery) -> str:
    parts = [
        query.brand,
        query.model,
        query.description,
        query.variant,
        query.size,
        query.color,
        *query.required_features,
    ]
    return " ".join(part for part in parts if part)


def score_candidate(query: PurchaseItemQuery, candidate: ProductCandidate) -> float:
    haystack = _tokens(candidate.title)
    if not haystack:
        return 0.0

    wanted_text = " ".join(
        part
        for part in [
            query.description,
            query.brand or "",
            query.model or "",
            query.variant or "",
            query.size or "",
            query.color or "",
            " ".join(query.required_features),
        ]
        if part
    )
    wanted = _tokens(wanted_text)
    overlap = len(wanted & haystack) / max(len(wanted), 1)

    bonus = 0.0
    for exact in (query.brand, query.model, query.variant, query.size, query.color):
        if exact and exact.lower() in candidate.title.lower():
            bonus += 0.08
    if candidate.price is not None:
        max_price = effective_max_price(query)
        if max_price is not None and candidate.price <= max_price:
            bonus += 0.05

    return min(overlap + bonus, 1.0)


def choose_candidate(query: PurchaseItemQuery, candidates: list[ProductCandidate]) -> tuple[str, ProductCandidate | None]:
    if not candidates:
        return "not_found", None

    scored = []
    for candidate in candidates:
        candidate.score = score_candidate(query, candidate)
        scored.append(candidate)
    scored.sort(key=lambda item: item.score, reverse=True)

    best = scored[0]
    if best.score < MIN_ACCEPT_SCORE:
        return "not_found", None
    if len(scored) > 1 and (best.score - scored[1].score) < AMBIGUOUS_SCORE_DELTA:
        return "ambiguous", best
    return "selected", best


def effective_max_price(query: PurchaseItemQuery) -> float | None:
    if query.max_price is not None:
        return query.max_price
    if DEFAULT_MAX_TOTAL:
        try:
            return float(DEFAULT_MAX_TOTAL)
        except ValueError:
            return None
    return None


def ensure_price_allowed(query: PurchaseItemQuery, price: float | None) -> None:
    max_price = effective_max_price(query)
    if max_price is None or price is None:
        return
    if price * query.quantity > max_price:
        raise ValueError(f"price {price * query.quantity:.2f} exceeds max_price {max_price:.2f}")


def parse_price(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"(\d+(?:,\d{3})*(?:\.\d{2})?)", text)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def _validate_stagehand_env() -> None:
    missing = [
        name
        for name in ("BROWSERBASE_API_KEY", "BROWSERBASE_PROJECT_ID", "BROWSERBASE_CONTEXT_ID", "MODEL_API_KEY")
        if not os.environ.get(name)
    ]
    if missing:
        raise StagehandConfigError(f"missing required Stagehand env vars: {', '.join(missing)}")


def _create_stagehand_client() -> Any:
    from stagehand import AsyncStagehand

    return AsyncStagehand(
        browserbase_api_key=os.environ["BROWSERBASE_API_KEY"],
        browserbase_project_id=os.environ["BROWSERBASE_PROJECT_ID"],
        model_api_key=os.environ["MODEL_API_KEY"],
    )


async def _create_stagehand_session(client: Any) -> Any:
    context_id = os.environ["BROWSERBASE_CONTEXT_ID"]
    session_params: dict[str, Any] = {
        "project_id": os.environ["BROWSERBASE_PROJECT_ID"],
        "browser_settings": {
            "block_ads": True,
            "record_session": True,
            "viewport": {"width": 1440, "height": 1000},
            "context": {"id": context_id, "persist": True},
        },
        "user_metadata": {"skill": "purchase_item", "runtime": "omegaclaw-agentverse"},
    }
    proxies = _browserbase_proxies()
    if proxies:
        session_params["proxies"] = proxies

    start = getattr(client.sessions, "start", None)
    if start is None:
        create = getattr(client.sessions, "create")
        return await create(
            model_name=STAGEHAND_MODEL_NAME,
            browser=STAGEHAND_BROWSER,
            dom_settle_timeout_ms=int(os.environ.get("STAGEHAND_DOM_SETTLE_TIMEOUT_MS", "5000")),
            verbose=int(os.environ.get("STAGEHAND_VERBOSE", "1")),
            browserbase_session_create_params=session_params,
        )

    response = await start(
        model_name=STAGEHAND_MODEL_NAME,
        browser=STAGEHAND_BROWSER,
        dom_settle_timeout_ms=int(os.environ.get("STAGEHAND_DOM_SETTLE_TIMEOUT_MS", "5000")),
        verbose=int(os.environ.get("STAGEHAND_VERBOSE", "1")),
        browserbase_session_create_params=session_params,
    )
    session_id = _session_id_from_start_response(response)
    if not session_id:
        raise StagehandConfigError("Stagehand did not return a Browserbase session ID")
    return StagehandSession(client=client, id=session_id)


def _session_id_from_start_response(response: Any) -> str:
    data = getattr(response, "data", None)
    if data is not None:
        return str(
            getattr(data, "session_id", None)
            or getattr(data, "sessionId", None)
            or getattr(data, "id", None)
            or ""
        )
    if isinstance(response, dict):
        data = response.get("data")
        if isinstance(data, dict):
            return str(data.get("sessionId") or data.get("session_id") or data.get("id") or "")
    return ""


def _browserbase_proxies() -> list[dict[str, Any]]:
    if os.environ.get("BROWSERBASE_USE_PROXY") != "1":
        return []
    return [_browserbase_proxy()]


def _browserbase_proxy() -> dict[str, Any]:
    proxy: dict[str, Any] = {"type": "browserbase"}
    city = os.environ.get("BROWSERBASE_PROXY_CITY")
    state = os.environ.get("BROWSERBASE_PROXY_STATE")
    country = os.environ.get("BROWSERBASE_PROXY_COUNTRY")
    geolocation = {
        key: value
        for key, value in {"city": city, "state": state, "country": country}.items()
        if value
    }
    if geolocation:
        proxy["geolocation"] = geolocation
    return proxy


def _session_info(session: Any) -> BrowserSessionInfo:
    session_id = str(
        getattr(session, "id", None)
        or getattr(session, "session_id", None)
        or getattr(getattr(session, "data", None), "session_id", None)
        or getattr(getattr(session, "data", None), "sessionId", None)
        or ""
    )
    return BrowserSessionInfo(
        session_id=session_id,
        recording_url=f"https://browserbase.com/sessions/{session_id}" if session_id else "",
    )


async def _extract_page_state(session: Any) -> dict[str, Any]:
    return await _extract_dict(
        session,
        instruction=(
            "Extract the current Amazon search results page state. Include whether sign-in is required, "
            "whether an anti-bot challenge is visible, the current URL, and up to 8 organic product results "
            "with title, URL, price text, numeric price if visible, and availability text."
        ),
        schema={
            "type": "object",
            "properties": {
                "current_url": {"type": "string"},
                "needs_auth": {"type": "boolean"},
                "blocked": {"type": "boolean"},
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "price": {"type": ["number", "null"]},
                            "price_text": {"type": ["string", "null"]},
                            "availability": {"type": ["string", "null"]},
                        },
                        "required": ["title"],
                    },
                },
            },
            "required": ["needs_auth", "blocked", "results"],
        },
    )


async def _extract_product_state(session: Any) -> dict[str, Any]:
    return await _extract_dict(
        session,
        instruction=(
            "Extract the current Amazon product page state. Include current URL, product title, visible price, "
            "whether sign-in is required, whether an anti-bot challenge is visible, and whether the product "
            "is currently unavailable or out of stock."
        ),
        schema={
            "type": "object",
            "properties": {
                "current_url": {"type": "string"},
                "product_title": {"type": "string"},
                "price": {"type": ["string", "number", "null"]},
                "needs_auth": {"type": "boolean"},
                "blocked": {"type": "boolean"},
                "unavailable": {"type": "boolean"},
                "availability": {"type": ["string", "null"]},
            },
            "required": ["needs_auth", "blocked", "unavailable"],
        },
    )


async def _extract_review_state(session: Any) -> dict[str, Any]:
    return await _extract_dict(
        session,
        instruction=(
            "Extract the current Amazon checkout or cart review page state. Include current URL, product title if "
            "visible, total or item price if visible, whether sign-in is required, and whether an anti-bot "
            "challenge is visible. Confirm this page is for review only and do not take any action."
        ),
        schema={
            "type": "object",
            "properties": {
                "current_url": {"type": "string"},
                "product_title": {"type": ["string", "null"]},
                "price": {"type": ["string", "number", "null"]},
                "needs_auth": {"type": "boolean"},
                "blocked": {"type": "boolean"},
            },
            "required": ["needs_auth", "blocked"],
        },
    )


async def _extract_dict(session: Any, *, instruction: str, schema: dict[str, Any]) -> dict[str, Any]:
    response = await session.extract(instruction=instruction, schema=schema)
    result = _response_result(response)
    return result if isinstance(result, dict) else {}


def _response_result(response: Any) -> Any:
    data = getattr(response, "data", None)
    if data is not None:
        return getattr(data, "result", None)
    if isinstance(response, dict):
        data = response.get("data")
        if isinstance(data, dict):
            return data.get("result")
    return None


def _candidates_from_page_state(page_state: dict[str, Any]) -> list[ProductCandidate]:
    raw_results = page_state.get("results")
    if not isinstance(raw_results, list):
        return []

    candidates: list[ProductCandidate] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        title = _as_str(item.get("title"))
        if not title:
            continue
        price_text = _as_str(item.get("price_text"))
        raw_price = item.get("price")
        price = float(raw_price) if isinstance(raw_price, int | float) else parse_price(price_text)
        candidates.append(
            ProductCandidate(
                title=title,
                url=_as_str(item.get("url")),
                price=price,
                price_text=price_text,
                availability=_as_str(item.get("availability")),
            )
        )
    return candidates


def _open_product_instruction(candidate: ProductCandidate) -> str:
    if candidate.url:
        return f"Open this Amazon product result: {candidate.url}"
    return f"Open the Amazon product result titled exactly or most closely: {candidate.title}"


def _set_quantity_instruction(quantity: int) -> str:
    if quantity <= 1:
        return "Ensure the product quantity is 1."
    return f"Set the product quantity to {quantity} if the quantity control is available."


def _state_needs_auth(state: dict[str, Any]) -> bool:
    return bool(state.get("needs_auth"))


def _state_is_blocked(state: dict[str, Any]) -> bool:
    return bool(state.get("blocked"))


def _product_unavailable(state: dict[str, Any]) -> bool:
    availability = _as_str(state.get("availability")).lower()
    return bool(state.get("unavailable")) or "unavailable" in availability or "out of stock" in availability


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _tokens(text: str) -> set[str]:
    ignored = {"the", "a", "an", "and", "or", "for", "with", "of", "to", "in", "on"}
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in ignored}


async def _end_session(session: Any) -> None:
    try:
        await session.end()
    except Exception:
        pass


def _needs_auth_result(query: PurchaseItemQuery, session: BrowserSessionInfo) -> PurchaseItemResult:
    return PurchaseItemResult(
        status="needs_auth",
        summary="Amazon asked for sign-in. Refresh the Browserbase context login before trying again.",
        confidence="low",
        quantity=query.quantity,
        browserbase_session_id=session.session_id,
        recording_url=session.recording_url,
    )


def _blocked_result(query: PurchaseItemQuery, session: BrowserSessionInfo) -> PurchaseItemResult:
    return PurchaseItemResult(
        status="blocked",
        summary="Amazon presented an anti-bot challenge before checkout review.",
        confidence="low",
        quantity=query.quantity,
        browserbase_session_id=session.session_id,
        recording_url=session.recording_url,
    )
