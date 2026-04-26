from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any


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


def _fallback_extract_reminder_request(text: str) -> dict[str, str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return {"datetime": "", "details": ""}

    body = re.sub(
        r"^(?:remind me|set a reminder|reminder for later|remember to)\b",
        "",
        normalized,
        flags=re.IGNORECASE,
    ).strip(" ,")

    time_patterns = [
        r"\bin \d+ (?:second|minute|hour|day)s?\b",
        r"\btomorrow(?: at \d{1,2}(?::\d{2})?\s*(?:am|pm)?)?\b",
        r"\btoday(?: at \d{1,2}(?::\d{2})?\s*(?:am|pm)?)?\b",
        r"\bnow\b",
    ]

    for pattern in time_patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if not match:
            continue
        datetime_text = match.group(0).strip()
        before = body[: match.start()].strip(" ,")
        after = body[match.end() :].strip(" ,")
        if before.lower().startswith("to "):
            before = before[3:].strip()
        if after.lower().startswith("to "):
            after = after[3:].strip()
        details = after or before
        return {"datetime": datetime_text, "details": details}

    if body.lower().startswith("to "):
        body = body[3:].strip()
    return {"datetime": "", "details": body}


def parse_datetime(datetime_str: str) -> datetime | None:
    if not datetime_str:
        return None

    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(datetime_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            continue

    today_match = re.search(
        r"^(today|tomorrow)(?: at (\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?$",
        datetime_str.strip(),
        re.IGNORECASE,
    )
    if today_match:
        day_word = today_match.group(1).lower()
        hour_text = today_match.group(2)
        minute_text = today_match.group(3)
        meridiem = (today_match.group(4) or "").lower()
        now = datetime.now(UTC)
        target = now + timedelta(days=1 if day_word == "tomorrow" else 0)
        hour = int(hour_text) if hour_text else target.hour
        minute = int(minute_text) if minute_text else 0
        if meridiem == "pm" and hour < 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
        return target.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if datetime_str.strip().lower() == "now":
        return datetime.now(UTC)

    match = re.search(r"in (\d+) (second|minute|hour|day)s?", datetime_str, re.IGNORECASE)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        now = datetime.now(UTC)
        if unit == "second":
            return now + timedelta(seconds=amount)
        if unit == "minute":
            return now + timedelta(minutes=amount)
        if unit == "hour":
            return now + timedelta(hours=amount)
        if unit == "day":
            return now + timedelta(days=amount)

    return None


def extract_reminder_request(text: str, *, client: Any | None = None) -> dict[str, str]:
    try:
        llm_client = client or _get_asi_client()
        response = llm_client.chat.completions.create(
            model="asi1",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an assistant that extracts only a JSON object from the user request. "
                        "Output must be valid JSON with keys datetime and details. "
                        "Use empty string for any missing value. Do not include markdown fences, explanation, or any text outside the JSON object. "
                        "Example output: {\"datetime\": \"2026-04-26 15:00\", \"details\": \"call mom\"}."
                    ),
                },
                {"role": "user", "content": text},
            ],
            max_tokens=300,
        )
        content = str(response.choices[0].message.content or "")
        normalized = _strip_json_text(content)
        parsed = json.loads(normalized)
    except Exception:
        return _fallback_extract_reminder_request(text)

    return {
        "datetime": str(parsed.get("datetime") or "").strip(),
        "details": str(parsed.get("details") or "").strip(),
    }
