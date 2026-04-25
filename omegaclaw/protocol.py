# Helpers for formatting OmegaClaw results as backend tool_event messages.
# These dicts get sent to the iOS client over the WebSocket.

import time
import uuid

def make_tool_event(tool_call_id: str, name: str, phase: str, args=None, result_summary=None, error=None) -> dict:
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

def new_tool_call_id() -> str:
    return str(uuid.uuid4())

def result_to_gemini_tool_response(tool_call_id: str, result: dict) -> dict:
    """Format an OmegaClaw skill result as a Gemini tool response part."""
    summary = result.get("summary") or result.get("description") or "No result."
    return {
        "tool_response": {
            "id": tool_call_id,
            "name": "identify_person",
            "response": {"summary": summary, "confidence": result.get("confidence", "low")},
        }
    }
