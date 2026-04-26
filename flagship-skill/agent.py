"""ASI:One-compatible purchase assistant agent.

This agent is intentionally thin: Agentverse handles chat discovery and
message delivery, while the Browserbase automation runs behind a worker URL.
That keeps the uploaded agent compatible with Hosted Agent import limits.
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
import os
from pathlib import Path
from uuid import uuid4

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

from models import PurchaseItemQuery, PurchaseItemResult, parse_purchase_query
from purchase_client import PurchaseClientError, invoke_purchase_worker


log = logging.getLogger(__name__)


def _load_local_env() -> None:
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_local_env()


AGENT_NAME = os.environ.get("PURCHASE_AGENT_NAME", "browserbase-purchase-agent")
AGENT_SEED = os.environ.get("AGENT_SEED", "browserbase-purchase-agent-dev-seed")
AGENT_PORT = int(os.environ.get("AGENT_PORT", "8001"))
AGENT_ENDPOINT = os.environ.get("AGENT_ENDPOINT")


def _agent_kwargs() -> dict:
    kwargs = {
        "name": AGENT_NAME,
        "seed": AGENT_SEED,
        "port": AGENT_PORT,
        "mailbox": os.environ.get("AGENT_MAILBOX", "true").lower() == "true",
        "publish_agent_details": os.environ.get("PUBLISH_AGENT_DETAILS", "true").lower() == "true",
    }
    if AGENT_ENDPOINT:
        kwargs["endpoint"] = [AGENT_ENDPOINT]
    return kwargs


agent = Agent(**_agent_kwargs())
chat_protocol = Protocol(spec=chat_protocol_spec)


def create_text_chat(text: str, *, end_session: bool = True) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.utcnow(), msg_id=uuid4(), content=content)


def _chat_text(msg: ChatMessage) -> str:
    chunks: list[str] = []
    for item in msg.content:
        if isinstance(item, TextContent):
            chunks.append(item.text)
    return "\n".join(chunks).strip()


def _result_text(result: PurchaseItemResult) -> str:
    if result.status == "review_ready":
        title = result.product_title or "the selected item"
        price = f" for {result.price}" if result.price else ""
        return (
            f"I found {title}{price}, added quantity {result.quantity} to the cart, "
            "and stopped at the Amazon checkout review page. I did not place the order."
        )
    return result.summary


@chat_protocol.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    text = _chat_text(msg)
    try:
        query = parse_purchase_query(text)
        result = await invoke_purchase_worker(query)
    except ValueError as exc:
        result = PurchaseItemResult(
            status="error",
            summary=f"I need a product description before I can prepare a purchase review. {exc}",
            confidence="low",
        )
    except PurchaseClientError as exc:
        ctx.logger.exception("purchase worker request failed")
        result = PurchaseItemResult(
            status="error",
            summary=f"I could not reach the Browserbase purchase worker: {exc}",
            confidence="low",
            error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        ctx.logger.exception("purchase request failed")
        result = PurchaseItemResult(
            status="error",
            summary="I could not prepare the Amazon checkout review right now.",
            confidence="low",
            error=str(exc),
        )

    payload = result.model_dump(exclude_none=True)
    await ctx.send(
        sender,
        create_text_chat(f"{_result_text(result)}\n\n```json\n{json.dumps(payload, indent=2)}\n```"),
    )


@agent.on_message(model=PurchaseItemQuery)
async def handle_purchase_query(ctx: Context, sender: str, msg: PurchaseItemQuery) -> None:
    try:
        result = await invoke_purchase_worker(msg)
    except Exception as exc:  # noqa: BLE001
        ctx.logger.exception("structured purchase request failed")
        result = PurchaseItemResult(
            status="error",
            summary="I could not prepare the Amazon checkout review right now.",
            confidence="low",
            error=str(exc),
        )
    await ctx.send(sender, result)


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    log.debug("ack from %s for %s", sender, msg.acknowledged_msg_id)


agent.include(chat_protocol, publish_manifest=True)


if __name__ == "__main__":
    agent.run()

