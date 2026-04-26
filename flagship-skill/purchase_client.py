"""Playwright MCP client loop used by the ASI:One purchase agent."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import os
from typing import Any, Protocol

from models import PurchaseItemQuery, PurchaseItemResult
from purchase_prompt import PURCHASE_AGENT_SYSTEM_PROMPT, render_purchase_agent_prompt


DEFAULT_PLAYWRIGHT_MCP_URL = "http://127.0.0.1:8931/mcp"
DEFAULT_PURCHASE_AGENT_MODEL = "gemini-2.5-flash"
DEFAULT_AGENT_MAX_STEPS = 16


class PurchaseClientError(RuntimeError):
    pass


@dataclass(slots=True)
class McpToolSpec:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ModelToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str | None = None


@dataclass(slots=True)
class ModelTurn:
    text: str = ""
    tool_calls: list[ModelToolCall] = field(default_factory=list)


class ToolCallingModel(Protocol):
    async def next_turn(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[McpToolSpec],
    ) -> ModelTurn:
        ...


async def invoke_purchase_worker(query: PurchaseItemQuery) -> PurchaseItemResult:
    return await invoke_purchase_tool(query)


async def invoke_purchase_tool(query: PurchaseItemQuery) -> PurchaseItemResult:
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError as exc:
        raise PurchaseClientError("missing MCP client dependency; run `uv sync`") from exc

    mcp_url = os.environ.get("PLAYWRIGHT_MCP_URL", DEFAULT_PLAYWRIGHT_MCP_URL)
    timeout_s = float(os.environ.get("PLAYWRIGHT_MCP_TIMEOUT_S") or os.environ.get("PURCHASE_MCP_TIMEOUT_S", "180"))
    model = GeminiToolModel.from_environment()

    try:
        async with streamablehttp_client(mcp_url, timeout=timeout_s) as streams:
            read_stream, write_stream, *_ = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                tools = [_tool_spec_from_mcp_tool(tool) for tool in tools_result.tools]
                if not tools:
                    raise PurchaseClientError("Playwright MCP returned no tools")
                return await _run_purchase_agent_loop(query, session, tools, model)
    except PurchaseClientError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PurchaseClientError(f"Playwright MCP purchase workflow failed: {exc}") from exc


class GeminiToolModel:
    """Small Gemini function-calling adapter for MCP tools."""

    def __init__(self, *, api_key: str, model_name: str) -> None:
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError as exc:  # pragma: no cover - depends on optional install state
            raise PurchaseClientError("missing Gemini dependency; run `uv sync`") from exc

        self._client = genai.Client(api_key=api_key)
        self._types = genai_types
        self._model_name = model_name

    @classmethod
    def from_environment(cls) -> GeminiToolModel:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("MODEL_API_KEY")
        if not api_key:
            raise PurchaseClientError("missing GEMINI_API_KEY or MODEL_API_KEY for purchase agent")
        model_name = os.environ.get("PURCHASE_AGENT_MODEL", DEFAULT_PURCHASE_AGENT_MODEL)
        return cls(api_key=api_key, model_name=model_name)

    async def next_turn(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[McpToolSpec],
    ) -> ModelTurn:
        return await asyncio.to_thread(
            self._next_turn_sync,
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
        )

    def _next_turn_sync(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[McpToolSpec],
    ) -> ModelTurn:
        config_kwargs: dict[str, Any] = {
            "system_instruction": system_prompt,
            "temperature": 0.1,
        }
        declarations = [self._function_declaration(tool) for tool in tools]
        if declarations:
            config_kwargs["tools"] = [self._types.Tool(function_declarations=declarations)]

        response = self._client.models.generate_content(
            model=self._model_name,
            contents=self._contents_from_messages(messages),
            config=self._types.GenerateContentConfig(**config_kwargs),
        )
        return self._turn_from_response(response)

    def _function_declaration(self, tool: McpToolSpec) -> Any:
        parameters = tool.input_schema or {"type": "object", "properties": {}}
        return self._types.FunctionDeclaration(
            name=tool.name,
            description=tool.description or tool.name,
            parameters=parameters,
        )

    def _contents_from_messages(self, messages: list[dict[str, Any]]) -> list[Any]:
        contents = []
        for message in messages:
            role = message["role"]
            if role == "user":
                contents.append(
                    self._types.Content(
                        role="user",
                        parts=[self._types.Part(text=str(message.get("content", "")))],
                    )
                )
                continue
            if role == "assistant":
                parts = []
                if message.get("content"):
                    parts.append(self._types.Part(text=str(message["content"])))
                for call in message.get("tool_calls", []):
                    parts.append(
                        self._types.Part(
                            function_call=self._types.FunctionCall(
                                name=call["name"],
                                args=call.get("arguments") or {},
                            )
                        )
                    )
                if parts:
                    contents.append(self._types.Content(role="model", parts=parts))
                continue
            if role == "tool":
                contents.append(
                    self._types.Content(
                        role="tool",
                        parts=[
                            self._types.Part.from_function_response(
                                name=str(message["tool_name"]),
                                response=message.get("content") or {},
                            )
                        ],
                    )
                )
        return contents

    @staticmethod
    def _turn_from_response(response: Any) -> ModelTurn:
        text_chunks: list[str] = []
        tool_calls: list[ModelToolCall] = []

        candidates = getattr(response, "candidates", None) or []
        if candidates:
            content = getattr(candidates[0], "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                text = getattr(part, "text", None)
                if text:
                    text_chunks.append(str(text))
                function_call = getattr(part, "function_call", None)
                if function_call is not None and getattr(function_call, "name", None):
                    raw_args = getattr(function_call, "args", None) or {}
                    tool_calls.append(
                        ModelToolCall(
                            name=str(function_call.name),
                            arguments=dict(raw_args),
                            call_id=str(getattr(function_call, "id", "") or "") or None,
                        )
                    )

        if not text_chunks and getattr(response, "text", None):
            text_chunks.append(str(response.text))
        return ModelTurn(text="\n".join(text_chunks).strip(), tool_calls=tool_calls)


async def _run_purchase_agent_loop(
    query: PurchaseItemQuery,
    session: Any,
    tools: list[McpToolSpec],
    model: ToolCallingModel,
    *,
    max_steps: int = DEFAULT_AGENT_MAX_STEPS,
    amazon_url: str | None = None,
) -> PurchaseItemResult:
    tool_names = {tool.name for tool in tools}
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": render_purchase_agent_prompt(
                query,
                amazon_url=amazon_url or os.environ.get("AMAZON_URL", "https://www.amazon.com"),
            ),
        }
    ]

    for _ in range(max_steps):
        turn = await model.next_turn(
            system_prompt=PURCHASE_AGENT_SYSTEM_PROMPT,
            messages=messages,
            tools=tools,
        )

        if turn.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": turn.text,
                    "tool_calls": [
                        {"name": call.name, "arguments": call.arguments, "call_id": call.call_id}
                        for call in turn.tool_calls
                    ],
                }
            )
            for call in turn.tool_calls:
                if call.name not in tool_names:
                    payload = {"error": f"unknown Playwright MCP tool: {call.name}"}
                else:
                    payload = await _call_mcp_tool(session, call)
                messages.append({"role": "tool", "tool_name": call.name, "content": payload})
            continue

        if turn.text.strip():
            return _purchase_result_from_final_text(turn.text, query)

        messages.append({"role": "user", "content": "Continue and return the final PurchaseItemResult JSON."})

    return PurchaseItemResult(
        status="error",
        summary="The purchase agent did not finish the Playwright MCP workflow before the step limit.",
        confidence="low",
        quantity=query.quantity,
        browser_profile="playwright-mcp",
        error="agent_step_limit",
    )


async def _call_mcp_tool(session: Any, call: ModelToolCall) -> dict[str, Any]:
    try:
        result = await session.call_tool(call.name, arguments=call.arguments)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    return _tool_result_payload(result)


def _purchase_result_from_final_text(text: str, query: PurchaseItemQuery) -> PurchaseItemResult:
    data = _parse_json_object(text)
    if data is None:
        return PurchaseItemResult(
            status="error",
            summary="The purchase agent returned a non-JSON final response.",
            confidence="low",
            quantity=query.quantity,
            browser_profile="playwright-mcp",
            error=text.strip()[:1000],
        )

    data.setdefault("quantity", query.quantity)
    data.setdefault("requires_confirmation", True)
    data.setdefault("browser_profile", "playwright-mcp")
    return PurchaseItemResult.model_validate(data)


def _parse_json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        chunks = [chunk.strip() for chunk in cleaned.split("```") if chunk.strip()]
        for chunk in chunks:
            if chunk.startswith("json"):
                chunk = chunk[4:].strip()
            parsed = _loads_json_object(chunk)
            if parsed is not None:
                return parsed
    return _loads_json_object(cleaned)


def _loads_json_object(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _tool_spec_from_mcp_tool(tool: Any) -> McpToolSpec:
    schema = getattr(tool, "inputSchema", None)
    if schema is None:
        schema = getattr(tool, "input_schema", None)
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump(exclude_none=True)
    if not isinstance(schema, dict):
        schema = {"type": "object", "properties": {}}
    return McpToolSpec(
        name=str(getattr(tool, "name", "")),
        description=str(getattr(tool, "description", "") or ""),
        input_schema=schema,
    )


def _tool_result_payload(result: Any) -> dict[str, Any]:
    if getattr(result, "isError", False):
        return {"error": _tool_result_text(result) or "MCP tool returned an error"}

    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured

    text = _tool_result_text(result)
    if text:
        parsed = _loads_json_object(text)
        return parsed if parsed is not None else {"text": text}
    return {"content": repr(result)}


def _tool_result_text(result: Any) -> str:
    chunks: list[str] = []
    for content in getattr(result, "content", []) or []:
        text = getattr(content, "text", None)
        if isinstance(text, str):
            chunks.append(text)
    return "\n".join(chunks).strip()
