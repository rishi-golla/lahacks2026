import asyncio
import json
import logging
import os
from typing import Any

from uagents import Model
from uagents.communication import send_message, send_sync_message
from uagents_core.types import DeliveryStatus, MsgStatus

log = logging.getLogger(__name__)

TECHNICAL_ANALYSIS_AGENT_ADDRESS = os.environ.get(
    "TECHNICAL_ANALYSIS_AGENT_ADDRESS",
    "agent1q085746wlr3u2uh4fmwqplude8e0w6fhrmqgsnlp49weawef3ahlutypvu6",
)
TAVILY_SEARCH_AGENT_ADDRESS = os.environ.get(
    "TAVILY_SEARCH_AGENT_ADDRESS",
    "agent1qt5uffgp0l3h9mqed8zh8vy5vs374jl2f8y0mjjvqm44axqseejqzmzx9v8",
)

# LA Hacks mail uAgent — override with MAIL_SENDING_AGENT_ADDRESS if needed.
MAIL_SENDING_AGENT_ADDRESS = os.environ.get(
    "MAIL_SENDING_AGENT_ADDRESS",
    "agent1qw6d5mxr6dsw859yxuuk8zg8wgg9j8x9ss230upu6z72pv60hvyyuuwhyaz",
).strip()

# LA Hacks reminder uAgent — override with REMINDER_AGENT_ADDRESS if needed.
REMINDER_AGENT_ADDRESS = os.environ.get(
    "REMINDER_AGENT_ADDRESS",
    "agent1qv37fkpxaeu538vxp2axmafehh7krvganh0ygqdnrnck35xpjdatwt6rult",
).strip()


class WebSearchRequest(Model):
    query: str


class TechAnalysisRequest(Model):
    ticker: str


class MailSendingRequest(Model):
    """Must match `MailSendingRequest` in `agents/mail_sending_agent.py`."""

    prompt: str


class ReminderRequest(Model):
    """Must match `ReminderRequest` in `agents/reminder_agent.py`."""

    prompt: str


def _truncate_text(value: Any, limit: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _format_tavily_results(response: str, max_results: int = 5) -> str:
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        return response

    if not isinstance(data, dict):
        return response

    results = data.get("results")
    if not isinstance(results, list):
        return response

    formatted = []
    for result in results[:max_results]:
        if not isinstance(result, dict):
            continue

        title = _truncate_text(result.get("title", ""), 160)
        url = _truncate_text(result.get("url", ""), 240)
        snippet = _truncate_text(result.get("content", ""), 400)

        parts = []
        if title:
            parts.append(f"TITLE: {title}")
        if url:
            parts.append(f"URL: {url}")
        if snippet:
            parts.append(f"SNIPPET: {snippet}")

        if parts:
            formatted.append(f"({' '.join(parts)})")

    return f"({' '.join(formatted)})" if formatted else response


async def _ask_agent_async_only(
    destination: str, request: Model, timeout: int = 60
) -> str:
    """Call a uAgent with **async** delivery only (``sync=False``).

    Use for skills that do not need a synchronous *reply* Envelope. Skipping
    ``send_sync_message`` avoids ``uagents`` parsing an invalid Agentverse **sync**
    response (HTTP 200 + empty body), which spams ``[dispenser]`` and Pydantic errors.
    """
    out: Any = await send_message(
        destination=destination,
        message=request,
        timeout=timeout,
        sync=False,
    )
    if isinstance(out, MsgStatus) and out.status == DeliveryStatus.DELIVERED:
        return (
            "Message delivered. The uAgent will process the request; "
            "there is no in-band reply in async mode."
        )
    return str(out)


async def _ask_agent(destination: str, request: Model, timeout: int = 60) -> str:
    """Call a remote uAgent.

    The outbound Envelope (version, sender, target, session, schema_digest, …) is built
    by ``uagents``. Sync mode expects a **full** Envelope in the HTTP response; Agentverse
    sometimes returns **200** with an empty object ``{}``, so Pydantic fails to parse
    the reply and the client surfaces ``MsgStatus(FAILED, …)``. In that case we retry
    with **async** delivery (``sync=False``) which only needs a delivered ack, not a
    well-formed response Envelope.
    """
    first: Any = await send_sync_message(
        destination=destination,
        message=request,
        timeout=timeout,
    )
    if isinstance(first, MsgStatus) and first.status == DeliveryStatus.FAILED:
        log.warning(
            "uagents sync send failed, retrying async: destination=%s detail=%r",
            destination,
            first.detail,
        )
        second: Any = await send_message(
            destination=destination,
            message=request,
            timeout=timeout,
            sync=False,
        )
        if isinstance(second, MsgStatus) and second.status == DeliveryStatus.DELIVERED:
            return (
                "[async] Message accepted for delivery. The mailbox did not return a valid "
                "synchronous Envelope, so a reply from the agent is not available in this path."
            )
        return str(second)
    return str(first)


def technical_analysis(ticker: str, timeout: int = 60) -> str:
    try:
        request = TechAnalysisRequest(ticker=ticker)
        return asyncio.run(
            _ask_agent(TECHNICAL_ANALYSIS_AGENT_ADDRESS, request, int(timeout))
        )
    except Exception as e:
        return f"error: {e}"


def tavily_search(search_query: str, timeout: int = 60) -> str:
    try:
        request = WebSearchRequest(query=search_query)
        response = asyncio.run(
            _ask_agent(TAVILY_SEARCH_AGENT_ADDRESS, request, int(timeout))
        )
        return _format_tavily_results(response)
    except Exception as e:
        return f"error: {e}"


def mail_sending_agent(prompt: str, timeout: int = 120) -> str:
    try:
        request = MailSendingRequest(prompt=prompt)
        return asyncio.run(
            _ask_agent_async_only(MAIL_SENDING_AGENT_ADDRESS, request, int(timeout))
        )
    except Exception as e:
        return f"error: {e}"


def reminder_agent(prompt: str, timeout: int = 120) -> str:
    try:
        request = ReminderRequest(prompt=prompt)
        return asyncio.run(
            _ask_agent_async_only(REMINDER_AGENT_ADDRESS, request, int(timeout))
        )
    except Exception as e:
        return f"error: {e}"
