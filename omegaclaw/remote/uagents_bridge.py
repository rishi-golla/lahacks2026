"""uAgents-based bridge to the deployed ContextLens Agentverse skill.

Uses the uAgents peer-to-peer protocol to query the deployed agent directly
rather than going through an HTTP intermediary.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

CONTEXTLENS_AGENT_ADDRESS = (
    "agent1qdy95pwgw3uvp2vgv8qjpdaykhtpmfcegpwqdk5leh2lg36tpq3c66zggm0"
)

try:
    from uagents import Model
    from uagents.query import query as _uagents_query

    class _PersonQuery(Model):
        name: str
        organization: str
        title: str = ""

    class _PersonContext(Model):
        summary: str
        confidence: str
        source: str = "gemini"

    _uagents_available = True
except Exception:  # noqa: BLE001
    _uagents_available = False
    log.warning("uagents not installed — uAgents P2P bridge disabled, will fall back to HTTP")


async def query_identify_person(
    name: str,
    organization: str,
    title: str,
    *,
    timeout: float = 30.0,
    agent_address: str = CONTEXTLENS_AGENT_ADDRESS,
) -> dict:
    """Send a PersonQuery to the deployed ContextLens Agentverse agent via uAgents P2P.

    Raises RuntimeError when uagents package is not installed (caller should fall back).
    Raises TimeoutError / Exception on network failure (caller should fall back).
    """
    if not _uagents_available:
        raise RuntimeError("uagents package not installed")

    response = await _uagents_query(
        destination=agent_address,
        message=_PersonQuery(name=name, organization=organization, title=title),
        timeout=timeout,
    )
    if response is None:
        raise TimeoutError(f"No response from agent {agent_address} within {timeout}s")

    ctx = _PersonContext.model_validate_json(response.decode_payload())
    return {
        "summary": ctx.summary,
        "confidence": ctx.confidence,
        "source": ctx.source,
    }
