from __future__ import annotations

import json
import re

from openai import AsyncOpenAI

from .models import Confidence, IdentifyPersonRequest, IdentifyPersonResponse, PersonResult, ToolBundle
from .settings import Settings

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?:\+?\d[\d .()\-]{7,}\d)")


class ResponseModelHarness:
    """Turns Apollo tool outputs into a short response suitable for glasses audio."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = (
            AsyncOpenAI(
                base_url=settings.asi_one_base_url,
                api_key=settings.asi_one_api_key,
                timeout=settings.asi_one_timeout_seconds,
            )
            if settings.asi_one_api_key
            else None
        )

    async def formulate(
        self,
        request: IdentifyPersonRequest,
        tools: ToolBundle,
    ) -> IdentifyPersonResponse:
        matched_person = tools.people[0] if tools.people else None
        confidence = _infer_confidence(request, matched_person, bool(tools.organizations))

        if not self._client:
            return _fallback_response(request, tools, matched_person, confidence)

        try:
            completion = await self._client.chat.completions.create(
                model=self._settings.asi_one_model,
                messages=[
                    {"role": "system", "content": _system_prompt()},
                    {"role": "user", "content": _user_prompt(request, tools, confidence)},
                ],
                max_tokens=self._settings.model_max_tokens,
                temperature=0.2,
            )
            content = completion.choices[0].message.content or ""
            return _parse_model_response(request, tools, matched_person, confidence, content)
        except Exception:
            return _fallback_response(request, tools, matched_person, confidence)


def _system_prompt() -> str:
    return """
You are the identify_person Agentverse skill for a smart-glasses assistant.
Use only the badge fields and tool results provided by Apollo tools.
Do not perform facial recognition. Do not reveal or infer private contact details.
If the result is ambiguous, say what you can confirm and what remains uncertain.
The user hears the response aloud, so keep the summary under 35 words.
Return JSON only with keys: summary, confidence, source.
confidence must be one of: high, medium, low.
""".strip()


def _user_prompt(request: IdentifyPersonRequest, tools: ToolBundle, confidence: Confidence) -> str:
    payload = {
        "badge_fields": request.model_dump(exclude_none=True),
        "suggested_confidence": confidence,
        "apollo_people_results": [
            person.model_dump(exclude_none=True, exclude={"score"}) for person in tools.people[: request.max_results]
        ],
        "apollo_organization_results": [
            org.model_dump(exclude_none=True) for org in tools.organizations[: request.max_results]
        ],
        "tool_errors": [
            {"tool": result.tool_name, "error": result.error}
            for result in tools.tool_results
            if not result.ok
        ],
    }
    return json.dumps(payload, ensure_ascii=True)


def _parse_model_response(
    request: IdentifyPersonRequest,
    tools: ToolBundle,
    matched_person: PersonResult | None,
    fallback_confidence: Confidence,
    content: str,
) -> IdentifyPersonResponse:
    parsed = _load_model_json(content)
    if parsed is None:
        parsed = {"summary": content, "confidence": fallback_confidence, "source": _source(tools)}

    summary = _redact(str(parsed.get("summary") or "")).strip()
    if not summary:
        return _fallback_response(request, tools, matched_person, fallback_confidence)

    confidence = parsed.get("confidence")
    if confidence not in {"high", "medium", "low"}:
        confidence = fallback_confidence

    return IdentifyPersonResponse(
        summary=summary,
        confidence=confidence,
        source=str(parsed.get("source") or _source(tools)),
        matched_person=matched_person,
        organizations=tools.organizations,
        tool_results=tools.tool_results,
    )


def _load_model_json(content: str) -> dict[str, object] | None:
    content = content.strip()
    candidates = [content]

    if content.startswith("```"):
        stripped = content.strip("`").strip()
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
        candidates.append(stripped)

    first_brace = content.find("{")
    last_brace = content.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        candidates.append(content[first_brace : last_brace + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _fallback_response(
    request: IdentifyPersonRequest,
    tools: ToolBundle,
    matched_person: PersonResult | None,
    confidence: Confidence,
) -> IdentifyPersonResponse:
    if not request.name:
        summary = "I need a readable name from the badge before I can identify this person."
        confidence = "low"
    elif matched_person:
        title = matched_person.title or request.title or "a professional"
        org = matched_person.organization_name or request.organization
        if org:
            summary = f"{matched_person.name or request.name} appears to be {title} at {org}."
        else:
            summary = f"{matched_person.name or request.name} appears to be {title}."
    elif tools.organizations:
        org = tools.organizations[0].name or request.organization
        summary = f"I found {org}, but I could not confidently match {request.name} to a person record."
        confidence = "low"
    else:
        role = f", {request.title}" if request.title else ""
        org = f" at {request.organization}" if request.organization else ""
        summary = f"{request.name}{role}{org}. I could not confirm a matching Apollo result."
        confidence = "low"

    return IdentifyPersonResponse(
        summary=_redact(summary),
        confidence=confidence,
        source=_source(tools),
        matched_person=matched_person,
        organizations=tools.organizations,
        tool_results=tools.tool_results,
    )


def _infer_confidence(
    request: IdentifyPersonRequest,
    matched_person: PersonResult | None,
    organization_found: bool,
) -> Confidence:
    if not request.name:
        return "low"
    if not matched_person:
        return "low"
    if matched_person.score >= 0.7:
        return "high"
    if matched_person.score >= 0.4 or organization_found:
        return "medium"
    return "low"


def _source(tools: ToolBundle) -> str:
    ok_tools = [result.tool_name for result in tools.tool_results if result.ok]
    if ok_tools:
        return "badge fields + " + ", ".join(ok_tools)
    return "badge fields"


def _redact(text: str) -> str:
    text = EMAIL_RE.sub("[redacted email]", text)
    return PHONE_RE.sub("[redacted phone]", text)
