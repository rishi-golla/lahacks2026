"""Standalone Agentverse task scheduling agent using a fixed Google Calendar account."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import requests

try:
    from uagents import Agent, Context, Model, Protocol
    from uagents_core.models import ErrorMessage
    from uagents_core.contrib.protocols.chat import (
        ChatAcknowledgement,
        ChatMessage,
        EndSessionContent,
        TextContent,
        chat_protocol_spec,
    )
except ImportError:  # pragma: no cover - test fallback
    class Context:  # type: ignore[override]
        logger: Any

    class Protocol:  # type: ignore[override]
        def __init__(self, spec: Any = None) -> None:
            self.spec = spec

        def on_message(self, _message_type: Any, replies: Any = None):
            def decorator(func):
                return func

            return decorator

    class Model:  # type: ignore[override]
        def __init__(self, **kwargs: Any) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

    class Agent:  # type: ignore[override]
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def include(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def run(self) -> None:
            raise RuntimeError("uagents is required to run this agent")

    @dataclass
    class TextContent:
        type: str
        text: str

    @dataclass
    class EndSessionContent:
        type: str

    @dataclass
    class ChatAcknowledgement:
        timestamp: Any
        acknowledged_msg_id: Any

    @dataclass
    class ChatMessage:
        timestamp: Any
        msg_id: Any
        content: list[Any]

    @dataclass
    class ErrorMessage:
        error: str

    chat_protocol_spec = object()


class TaskSchedulingRequest(Model):
    prompt: str


class TaskSchedulingResponse(Model):
    summary: str
    start_iso: str
    end_iso: str
    event_id: str
    status: str


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_asi_client() -> Any:
    from openai import OpenAI

    return OpenAI(base_url="https://api.asi1.ai/v1", api_key=_require_env("ASI1_API_KEY"))


def extract_schedule_request(text: str, *, client: Any | None = None) -> dict[str, str]:
    llm_client = client or _get_asi_client()
    response = llm_client.chat.completions.create(
        model="asi1",
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract a scheduling request into JSON with summary, start_iso, end_iso, and details. "
                    "Return only JSON."
                ),
            },
            {"role": "user", "content": text},
        ],
        max_tokens=400,
    )
    parsed = json.loads(str(response.choices[0].message.content))
    return {
        "summary": str(parsed.get("summary", "")),
        "start_iso": str(parsed.get("start_iso", "")),
        "end_iso": str(parsed.get("end_iso", "")),
        "details": str(parsed.get("details", "")),
    }


def create_calendar_event(*, summary: str, start_iso: str, end_iso: str, description: str) -> str:
    token_uri = os.environ.get("GCAL_TOKEN_URI", "https://oauth2.googleapis.com/token")
    token_response = requests.post(
        token_uri,
        data={
            "client_id": _require_env("GCAL_CLIENT_ID"),
            "client_secret": _require_env("GCAL_CLIENT_SECRET"),
            "refresh_token": _require_env("GCAL_REFRESH_TOKEN"),
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    token_response.raise_for_status()
    access_token = str(token_response.json()["access_token"])
    calendar_id = os.environ.get("GCAL_CALENDAR_ID", "primary")

    event_response = requests.post(
        f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_iso},
            "end": {"dateTime": end_iso},
        },
        timeout=20,
    )
    event_response.raise_for_status()
    return str(event_response.json()["id"])


agent = Agent(
    name="task_scheduling_agent",
    seed=os.environ.get("AGENT_SEED_PHRASE", "task scheduling agentlahackss"),
    port=int(os.environ.get("TASK_SCHEDULING_AGENT_PORT", "8003")),
    mailbox=True,
    publish_agent_details=True,
)

protocol = Protocol(spec=chat_protocol_spec)


@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text

    try:
        payload = extract_schedule_request(text)
        summary = payload.get("summary", "").strip()
        if not summary:
            response_text = "What should I schedule?"
        else:
            create_calendar_event(
                summary=summary,
                start_iso=payload.get("start_iso", ""),
                end_iso=payload.get("end_iso", ""),
                description=payload.get("details", ""),
            )
            response_text = f"Done — I scheduled {summary}."
    except Exception:  # noqa: BLE001
        ctx.logger.exception("Error handling scheduling request")
        response_text = "I couldn't schedule that right now."

    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(UTC),
            msg_id=uuid4(),
            content=[
                TextContent(type="text", text=response_text),
                EndSessionContent(type="end-session"),
            ],
        ),
    )


@protocol.on_message(TaskSchedulingRequest, replies={TaskSchedulingResponse, ErrorMessage})
async def handle_task_scheduling_request(ctx: Context, sender: str, msg: TaskSchedulingRequest):
    try:
        payload = extract_schedule_request(msg.prompt)
        summary = payload.get("summary", "").strip()
        if not summary:
            await ctx.send(sender, ErrorMessage(error="Event summary is required."))
            return

        event_id = create_calendar_event(
            summary=summary,
            start_iso=payload.get("start_iso", ""),
            end_iso=payload.get("end_iso", ""),
            description=payload.get("details", ""),
        )
        await ctx.send(
            sender,
            TaskSchedulingResponse(
                summary=summary,
                start_iso=payload.get("start_iso", ""),
                end_iso=payload.get("end_iso", ""),
                event_id=event_id,
                status="Event scheduled successfully.",
            ),
        )
    except Exception:  # noqa: BLE001
        ctx.logger.exception("Error handling structured scheduling request")
        await ctx.send(
            sender,
            ErrorMessage(error="An error occurred while processing the scheduling request."),
        )


agent.include(protocol, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
