"""Formatting helpers for OmegaClaw loop tool events and responses."""

import uuid
from typing import Any


def make_tool_event(
    tool_call_id: str,
    name: str,
    phase: str,
    *,
    args: dict[str, Any] | None = None,
    result_summary: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    if not tool_call_id:
        raise ValueError("tool_call_id is required")
    if not name:
        raise ValueError("name is required")
    if phase not in {"started", "result", "error"}:
        raise ValueError("phase must be one of: started, result, error")

    event = {
        "type": "tool_event",
        "tool_call_id": tool_call_id,
        "name": name,
        "phase": phase,
    }
    if args is not None:
        event["args"] = args
    if result_summary is not None:
        event["result_summary"] = result_summary
    if error is not None:
        event["error"] = error
    return event


def make_loop_response(
    request_id: str,
    tool_call_id: str,
    skill_name: str,
    result: dict[str, Any],
    *,
    args: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    events = [make_tool_event(tool_call_id, skill_name, "started", args=args)]
    if error:
        events.append(make_tool_event(tool_call_id, skill_name, "error", error=error))
    else:
        summary = str(result.get("summary") or result.get("description") or "Completed")
        events.append(make_tool_event(tool_call_id, skill_name, "result", result_summary=summary))

    return {
        "request_id": request_id,
        "tool_call_id": tool_call_id,
        "skill_name": skill_name,
        "events": events,
        "result": result,
    }


def new_tool_call_id() -> str:
    return str(uuid.uuid4())


def result_to_gemini_tool_response(
    tool_call_id: str,
    tool_name: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Format an OmegaClaw skill result as a Gemini tool response part."""
    summary = result.get("summary") or result.get("description") or "No result."
    return {
        "tool_response": {
            "id": tool_call_id,
            "name": tool_name,
            "response": {"summary": summary, "confidence": result.get("confidence", "low")},
        }
    }
