"""Standalone Agentverse task scheduling agent using a fixed Google Calendar account."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


def _strip_json_text(content: str) -> str:
    if not content:
        return ""

    content = content.strip()
    lines = content.splitlines()
    if lines and lines[0].strip().startswith("```"):
        if lines[-1].strip().startswith("```"):
            content = "\n".join(lines[1:-1]).strip()
    if content.startswith("json\n"):
        content = content[len("json\n"):].strip()

    start = content.find("{")
    if start == -1:
        return content

    depth = 0
    for idx, char in enumerate(content[start:], start=start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return content[start : idx + 1]

    return content[start:]


def _fallback_extract_schedule_request(text: str) -> dict[str, str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    return {
        "summary": normalized,
        "start_iso": "",
        "end_iso": "",
        "details": "",
    }


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
    content = str(response.choices[0].message.content or "")
    normalized = _strip_json_text(content)
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError:
        parsed = _fallback_extract_schedule_request(text)
    return {
        "summary": str(parsed.get("summary", "")),
        "start_iso": str(parsed.get("start_iso", "")),
        "end_iso": str(parsed.get("end_iso", "")),
        "details": str(parsed.get("details", "")),
    }


def _second_sunday_of_march(year: int) -> int:
    march_first = datetime(year, 3, 1)
    first_sunday = 1 + ((6 - march_first.weekday()) % 7)
    return first_sunday + 7


def _first_sunday_of_november(year: int) -> int:
    november_first = datetime(year, 11, 1)
    return 1 + ((6 - november_first.weekday()) % 7)


def _is_us_dst(active_date: datetime) -> bool:
    start_day = _second_sunday_of_march(active_date.year)
    end_day = _first_sunday_of_november(active_date.year)
    start = datetime(active_date.year, 3, start_day, 2, 0, 0)
    end = datetime(active_date.year, 11, end_day, 2, 0, 0)
    naive_active = active_date.replace(tzinfo=None)
    return start <= naive_active < end


def _fallback_timezone(timezone_name: str, reference_utc: datetime | None = None) -> tzinfo:
    normalized = (timezone_name or "UTC").strip()
    if normalized.upper() == "UTC":
        return UTC

    no_dst_offsets = {
        "America/Phoenix": -7,
    }
    if normalized in no_dst_offsets:
        return timezone(timedelta(hours=no_dst_offsets[normalized]), name=normalized)

    us_zone_offsets = {
        "America/Los_Angeles": (-8, -7),
        "America/Denver": (-7, -6),
        "America/Chicago": (-6, -5),
        "America/New_York": (-5, -4),
    }
    if normalized in us_zone_offsets:
        standard_offset, daylight_offset = us_zone_offsets[normalized]
        utc_now = reference_utc or datetime.now(UTC)
        standard_local = utc_now.astimezone(timezone(timedelta(hours=standard_offset)))
        offset = daylight_offset if _is_us_dst(standard_local) else standard_offset
        return timezone(timedelta(hours=offset), name=normalized)

    return UTC


def _resolve_timezone(timezone_name: str) -> tzinfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return _fallback_timezone(timezone_name)


def _now_in_timezone(timezone_name: str) -> datetime:
    return datetime.now(_resolve_timezone(timezone_name))


def _parse_relative_date_phrase(text: str, timezone_name: str) -> tuple[str, str] | None:
    lowered = re.sub(r"\s+", " ", text.lower()).strip()
    now = _now_in_timezone(timezone_name)

    match = re.search(r"\b(today|tomorrow)\b(?: at (\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", lowered)
    if not match:
        return None

    day_word = match.group(1)
    hour_text = match.group(2)
    minute_text = match.group(3)
    meridiem = (match.group(4) or "").lower()

    target = now + timedelta(days=1 if day_word == "tomorrow" else 0)
    hour = int(hour_text) if hour_text else target.hour
    minute = int(minute_text) if minute_text else 0
    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0

    start = target.replace(hour=hour, minute=minute, second=0, microsecond=0)
    end = start + timedelta(hours=1)
    return start.strftime("%Y-%m-%dT%H:%M:%S"), end.strftime("%Y-%m-%dT%H:%M:%S")


def normalize_schedule_payload(text: str, payload: dict[str, str], timezone_name: str) -> dict[str, str]:
    normalized = dict(payload)
    resolved = _parse_relative_date_phrase(text, timezone_name)
    if resolved is not None:
        normalized["start_iso"], normalized["end_iso"] = resolved
    return normalized


def _calendar_time_payload(value: str, default_tz: str) -> dict[str, str]:
    normalized = str(value or "").strip()
    if not normalized:
        return {"dateTime": normalized, "timeZone": default_tz}

    # If the timestamp already carries offset info, Calendar can infer the zone.
    if normalized.endswith("Z") or re.search(r"[+-]\d{2}:\d{2}$", normalized):
        return {"dateTime": normalized, "timeZone": default_tz}

    return {"dateTime": normalized, "timeZone": default_tz}


def create_calendar_event(*, summary: str, start_iso: str, end_iso: str, description: str) -> dict[str, Any]:
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
    try:
        token_response.raise_for_status()
    except requests.HTTPError as exc:
        detail = getattr(token_response, "text", "")
        raise RuntimeError(f"Failed to refresh Google Calendar token: {detail or exc}") from exc
    access_token = str(token_response.json()["access_token"])
    calendar_id = os.environ.get("GCAL_CALENDAR_ID", "primary")
    calendar_tz = os.environ.get("GCAL_TIMEZONE", "UTC")

    start_payload = _calendar_time_payload(start_iso, calendar_tz)
    end_payload = _calendar_time_payload(end_iso, calendar_tz)

    event_response = requests.post(
        f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "summary": summary,
            "description": description,
            "start": start_payload,
            "end": end_payload,
        },
        timeout=20,
    )
    try:
        event_response.raise_for_status()
    except requests.HTTPError as exc:
        detail = getattr(event_response, "text", "")
        raise RuntimeError(f"Failed to create Google Calendar event: {detail or exc}") from exc
    return {
        "event_id": str(event_response.json()["id"]),
        "calendar_id": calendar_id,
        "calendar_tz": calendar_tz,
        "start": start_payload,
        "end": end_payload,
    }


agent = Agent(
    name="task_scheduling_agent",
    seed=os.environ.get("AGENT_SEED_PHRASE", "task scheduling agentlahackss"),
    port=int(os.environ.get("TASK_SCHEDULING_AGENT_PORT", "8003")),
    mailbox=True,
    publish_agent_details=True,
)

protocol = Protocol(spec=chat_protocol_spec)
request_protocol = Protocol()


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
        calendar_tz = os.environ.get("GCAL_TIMEZONE", "UTC")
        payload = normalize_schedule_payload(text, extract_schedule_request(text), calendar_tz)
        summary = payload.get("summary", "").strip()
        if not summary:
            response_text = "What should I schedule?"
        else:
            event_result = create_calendar_event(
                summary=summary,
                start_iso=payload.get("start_iso", ""),
                end_iso=payload.get("end_iso", ""),
                description=payload.get("details", ""),
            )
            response_text = (
                f"Done - I scheduled {summary} on {event_result['calendar_id']} "
                f"from {event_result['start']['dateTime']} to {event_result['end']['dateTime']} "
                f"({event_result['calendar_tz']}). Event ID: {event_result['event_id']}."
            )
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


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    return None


@request_protocol.on_message(TaskSchedulingRequest, replies={TaskSchedulingResponse, ErrorMessage})
async def handle_task_scheduling_request(ctx: Context, sender: str, msg: TaskSchedulingRequest):
    try:
        calendar_tz = os.environ.get("GCAL_TIMEZONE", "UTC")
        payload = normalize_schedule_payload(msg.prompt, extract_schedule_request(msg.prompt), calendar_tz)
        summary = payload.get("summary", "").strip()
        if not summary:
            await ctx.send(sender, ErrorMessage(error="Event summary is required."))
            return

        event_result = create_calendar_event(
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
                event_id=str(event_result["event_id"]),
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
agent.include(request_protocol, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
