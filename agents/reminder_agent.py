"""Standalone Agentverse reminder agent."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

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


class ReminderRequest(Model):
    prompt: str


class ReminderResponse(Model):
    datetime: str
    details: str
    status: str


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_asi_client() -> Any:
    from openai import OpenAI

    return OpenAI(base_url="https://api.asi1.ai/v1", api_key=_require_env("ASI1_API_KEY"))


def extract_reminder_request(text: str, *, client: Any | None = None) -> dict[str, str]:
    llm_client = client or _get_asi_client()
    response = llm_client.chat.completions.create(
        model="asi1",
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract a reminder request into JSON with datetime and details. "
                    "Return only JSON."
                ),
            },
            {"role": "user", "content": text},
        ],
        max_tokens=300,
    )
    parsed = json.loads(str(response.choices[0].message.content))
    return {
        "datetime": str(parsed.get("datetime", "")),
        "details": str(parsed.get("details", "")),
    }


agent = Agent(
    name="reminder_agent",
    seed=os.environ.get("AGENT_SEED_PHRASE", "reminder agentlahackss"),
    port=int(os.environ.get("REMINDER_AGENT_PORT", "8002")),
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
        payload = extract_reminder_request(text)
        if not payload.get("details", "").strip():
            response_text = "What should I remind you about?"
        else:
            response_text = (
                f"Done — I set a reminder for {payload.get('datetime', 'the requested time')} "
                f"to {payload['details']}."
            )
    except Exception:  # noqa: BLE001
        ctx.logger.exception("Error handling reminder request")
        response_text = "I couldn't set that reminder right now."

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


@protocol.on_message(ReminderRequest, replies={ReminderResponse, ErrorMessage})
async def handle_reminder_request(ctx: Context, sender: str, msg: ReminderRequest):
    try:
        payload = extract_reminder_request(msg.prompt)
        details = payload.get("details", "").strip()
        if not details:
            await ctx.send(sender, ErrorMessage(error="Reminder details are required."))
            return

        await ctx.send(
            sender,
            ReminderResponse(
                datetime=payload.get("datetime", ""),
                details=details,
                status="Reminder set successfully.",
            ),
        )
    except Exception:  # noqa: BLE001
        ctx.logger.exception("Error handling structured reminder request")
        await ctx.send(
            sender,
            ErrorMessage(error="An error occurred while processing the reminder request."),
        )


agent.include(protocol, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
