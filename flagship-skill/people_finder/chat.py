from __future__ import annotations

import json
import re
from typing import Any

from .models import IdentifyPersonRequest, IdentifyPersonResponse


def parse_chat_request(text: str, max_results: int) -> IdentifyPersonRequest:
    text = text.strip()
    if not text:
        return IdentifyPersonRequest(raw_query=None, max_results=max_results)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        return _from_mapping(parsed, raw_query=text, max_results=max_results)

    inferred = _parse_natural_query(text)
    return IdentifyPersonRequest(raw_query=text, max_results=max_results, **inferred)


def format_chat_response(response: IdentifyPersonResponse) -> str:
    return f"{response.summary} Confidence: {response.confidence}. Source: {response.source}."


def _from_mapping(data: dict[str, Any], raw_query: str, max_results: int) -> IdentifyPersonRequest:
    return IdentifyPersonRequest(
        name=data.get("name") or data.get("person_name"),
        organization=data.get("organization") or data.get("company") or data.get("org"),
        title=data.get("title") or data.get("job_title") or data.get("role"),
        domain=data.get("domain") or data.get("company_domain"),
        location=data.get("location"),
        raw_query=data.get("raw_query") or raw_query,
        max_results=int(data.get("max_results") or max_results),
    )


def _parse_natural_query(text: str) -> dict[str, str]:
    cleaned = text.strip().strip("?")
    patterns = [
        r"^(?:who is|identify|tell me about)\s+(?P<name>.+?)\s+(?:from|at|with)\s+(?P<organization>.+)$",
        r"^(?P<name>.+?)\s*,\s*(?P<title>.+?)\s*,\s*(?P<organization>.+)$",
        r"^(?P<name>.+?)\s+-\s+(?P<title>.+?)\s+-\s+(?P<organization>.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            return {key: value.strip() for key, value in match.groupdict().items() if value}
    return {}
