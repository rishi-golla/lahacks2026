from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from uagents import Agent, Context, Model, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

from people_finder.chat import format_chat_response, parse_chat_request
from people_finder.harness import PeopleFinderHarness
from people_finder.models import IdentifyPersonRequest
from people_finder.settings import Settings


class IdentifyPersonQuery(Model):
    name: str | None = None
    organization: str | None = None
    title: str | None = None
    domain: str | None = None
    location: str | None = None


class IdentifyPersonResult(Model):
    summary: str
    confidence: str
    source: str


settings = Settings()
if not settings.person_agent_seed:
    raise RuntimeError("PERSON_AGENT_SEED must be set for a stable Agentverse address")

harness = PeopleFinderHarness(settings)

agent = Agent(
    name=settings.person_agent_name,
    seed=settings.person_agent_seed,
    port=settings.person_agent_port,
    mailbox=settings.person_agent_mailbox,
    publish_agent_details=settings.publish_agent_details,
)

chat_protocol = Protocol(spec=chat_protocol_spec)


@chat_protocol.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    text = "".join(item.text for item in msg.content if isinstance(item, TextContent))
    request = parse_chat_request(text, max_results=settings.max_tool_results)
    response = await harness.identify(request)

    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[
                TextContent(type="text", text=format_chat_response(response)),
                EndSessionContent(type="end-session"),
            ],
        ),
    )


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    ctx.logger.debug("chat acknowledgement sender=%s msg_id=%s", sender, msg.acknowledged_msg_id)


@agent.on_message(model=IdentifyPersonQuery)
async def handle_structured_query(ctx: Context, sender: str, msg: IdentifyPersonQuery) -> None:
    request = IdentifyPersonRequest(
        name=msg.name,
        organization=msg.organization,
        title=msg.title,
        domain=msg.domain,
        location=msg.location,
        max_results=settings.max_tool_results,
    )
    response = await harness.identify(request)
    await ctx.send(
        sender,
        IdentifyPersonResult(
            summary=response.summary,
            confidence=response.confidence,
            source=response.source,
        ),
    )


agent.include(chat_protocol, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
