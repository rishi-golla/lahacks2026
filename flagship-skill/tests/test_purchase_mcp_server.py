from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models import PurchaseItemQuery  # noqa: E402
from purchase_client import (  # noqa: E402
    DEFAULT_PLAYWRIGHT_MCP_URL,
    McpToolSpec,
    ModelToolCall,
    ModelTurn,
    _run_purchase_agent_loop,
)


def test_playwright_agent_loop_returns_review_ready_after_tool_use() -> None:
    session = _FakeMcpSession()
    model = _FakeModel(
        [
            ModelTurn(
                tool_calls=[
                    ModelToolCall(
                        name="browser_navigate",
                        arguments={"url": "https://www.amazon.com/s?k=usb-c+cable"},
                    )
                ]
            ),
            ModelTurn(
                text=json.dumps(
                    {
                        "status": "review_ready",
                        "summary": "Amazon checkout review is ready. The order was not placed.",
                        "confidence": "high",
                        "product_title": "Anker USB-C Cable",
                        "product_url": "https://www.amazon.com/dp/example",
                        "price": "$9.99",
                        "checkout_url": "https://www.amazon.com/gp/buy/spc/handlers/display.html",
                    }
                )
            ),
        ]
    )

    result = asyncio.run(_run_purchase_agent_loop(_query(), session, _tools(), model))

    assert result.status == "review_ready"
    assert result.requires_confirmation is True
    assert result.quantity == 2
    assert result.browser_profile == "playwright-mcp"
    assert session.calls == [("browser_navigate", {"url": "https://www.amazon.com/s?k=usb-c+cable"})]
    assert any(message["role"] == "tool" for message in model.requests[-1]["messages"])


def test_playwright_agent_loop_returns_needs_auth() -> None:
    model = _FakeModel(
        [
            ModelTurn(
                text=json.dumps(
                    {
                        "status": "needs_auth",
                        "summary": "Amazon asked for sign-in in the local browser.",
                        "confidence": "low",
                    }
                )
            )
        ]
    )

    result = asyncio.run(_run_purchase_agent_loop(_query(), _FakeMcpSession(), _tools(), model))

    assert result.status == "needs_auth"
    assert result.quantity == 2


def test_playwright_agent_loop_returns_ambiguous_candidates() -> None:
    model = _FakeModel(
        [
            ModelTurn(
                text=json.dumps(
                    {
                        "status": "ambiguous",
                        "summary": "Multiple USB-C cables matched the request.",
                        "confidence": "medium",
                        "candidates": [
                            {"title": "USB-C cable black", "price": 8.99, "score": 0.71},
                            {"title": "USB-C cable white", "price": 8.99, "score": 0.7},
                        ],
                    }
                )
            )
        ]
    )

    result = asyncio.run(_run_purchase_agent_loop(_query(), _FakeMcpSession(), _tools(), model))

    assert result.status == "ambiguous"
    assert len(result.candidates) == 2


def test_playwright_agent_loop_converts_malformed_final_json_to_error() -> None:
    model = _FakeModel([ModelTurn(text="I clicked around and it worked.")])

    result = asyncio.run(_run_purchase_agent_loop(_query(), _FakeMcpSession(), _tools(), model))

    assert result.status == "error"
    assert result.error == "I clicked around and it worked."


@pytest.mark.integration
def test_running_playwright_mcp_exposes_browser_tools_over_streamable_http() -> None:
    _load_dotenv()
    if os.environ.get("LIVE_PLAYWRIGHT_MCP") != "1":
        pytest.skip("set LIVE_PLAYWRIGHT_MCP=1 with a running Playwright MCP HTTP server")

    url = os.environ.get("PLAYWRIGHT_MCP_URL", DEFAULT_PLAYWRIGHT_MCP_URL)
    tool_names = asyncio.run(_list_mcp_tools(url))

    assert "browser_navigate" in tool_names
    assert "browser_snapshot" in tool_names


async def _list_mcp_tools(url: str) -> set[str]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(url) as streams:
        read_stream, write_stream, *_ = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            return {tool.name for tool in tools.tools}


def _query() -> PurchaseItemQuery:
    return PurchaseItemQuery(description="USB-C charging cable 6ft", quantity=2, max_price=20)


def _tools() -> list[McpToolSpec]:
    return [
        McpToolSpec(
            name="browser_navigate",
            description="Navigate to a URL",
            input_schema={"type": "object", "properties": {"url": {"type": "string"}}},
        ),
        McpToolSpec(name="browser_snapshot", description="Read the accessibility snapshot"),
    ]


class _FakeMcpSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        return SimpleNamespace(content=[SimpleNamespace(text="snapshot ok")])


class _FakeModel:
    def __init__(self, turns: list[ModelTurn]) -> None:
        self._turns = turns
        self.requests: list[dict[str, Any]] = []

    async def next_turn(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[McpToolSpec],
    ) -> ModelTurn:
        self.requests.append(
            {
                "system_prompt": system_prompt,
                "messages": [dict(message) for message in messages],
                "tools": tools,
            }
        )
        return self._turns.pop(0)


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
