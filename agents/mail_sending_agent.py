"""Standalone Agentverse Gmail sending agent.

Required environment variables:
- ASI1_API_KEY
- GMAIL_SENDER_EMAIL
- GMAIL_CLIENT_ID
- GMAIL_CLIENT_SECRET
- GMAIL_REFRESH_TOKEN

Run with:
- `python agents/mail_sending_agent.py`
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.mime.text import MIMEText
from typing import Any
from uuid import uuid4

import requests

_SIGNATURE_IMAGE_URL = (
    "https://res.cloudinary.com/fetch-ai/image/upload/v1775063969/fetch-llm/onboarding/4_mkezrr.png"
)

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


class MailSendingRequest(Model):
    prompt: str


class MailSendingResponse(Model):
    recipient: str
    subject: str
    message_id: str
    status: str


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_asi_client() -> Any:
    from openai import OpenAI

    return OpenAI(
        base_url="https://api.asi1.ai/v1",
        api_key=_require_env("ASI1_API_KEY"),
    )


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


def _extract_email_address(text: str) -> str:
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return match.group(0) if match else ""


def _fallback_extract_email_request(text: str) -> dict[str, str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    recipient = _extract_email_address(normalized)
    body_intent = normalized
    if recipient:
        body_intent = re.sub(re.escape(recipient), "", body_intent, flags=re.IGNORECASE).strip(" ,.")
    body_intent = re.sub(r"^(send|draft|email|mail)\s+(an?\s+)?email\s+(to\s+)?", "", body_intent, flags=re.IGNORECASE)
    body_intent = re.sub(r"^(send|draft|email|mail)\s+", "", body_intent, flags=re.IGNORECASE)
    return {
        "recipient": recipient,
        "subject_hint": "",
        "body_intent": body_intent.strip() or normalized,
    }


def extract_email_request(text: str, *, client: Any | None = None) -> dict[str, str]:
    llm_client = client or _get_asi_client()
    try:
        response = llm_client.chat.completions.create(
            model="asi1",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an assistant that extracts only a JSON object from the user request. "
                        "Output must be valid JSON with keys recipient, subject_hint, and body_intent. "
                        "Use empty string for any missing value. Do not include markdown fences, explanation, or any text outside the JSON object. "
                        "Example output: {\"recipient\": \"lucaskamadakim@gmail.com\", \"subject_hint\": \"hi\", \"body_intent\": \"saying hi\"}."
                    ),
                },
                {"role": "user", "content": text},
            ],
            max_tokens=400,
            timeout=12,
        )
        content = str(response.choices[0].message.content or "")
        normalized = _strip_json_text(content)
        parsed = json.loads(normalized)
    except Exception:  # noqa: BLE001
        parsed = _fallback_extract_email_request(text)

    recipient = str(parsed.get("recipient") or "").strip()
    if not recipient:
        recipient = _extract_email_address(text)

    return {
        "recipient": recipient,
        "subject_hint": str(parsed.get("subject_hint") or "").strip(),
        "body_intent": str(parsed.get("body_intent") or "").strip(),
    }


def build_html_email(payload: dict[str, Any]) -> tuple[str, str]:
    subject_hint = str(payload.get("subject_hint") or "A quick note from Edith")
    body_intent = str(payload.get("body_intent") or "Hello from Edith.")

    subject = f"Small orbit, big hello: {subject_hint}"
    body = (
        f"<p>{body_intent}</p>"
        "<p>Warmly,<br>Rishi Golla</p>"
        f"<p><img src=\"{_SIGNATURE_IMAGE_URL}\" width=\"36\" height=\"36\" "
        "alt=\"Edith icon\" style=\"vertical-align:middle;\"> "
        "Sent by Edith, my AI Agent</p>"
        "<p>www.asi1.ai</p>"
    )
    return subject, body


def send_gmail_message(*, recipient: str, subject: str, html_body: str) -> str:
    token_uri = os.environ.get("GMAIL_TOKEN_URI", "https://oauth2.googleapis.com/token")
    token_response = requests.post(
        token_uri,
        data={
            "client_id": _require_env("GMAIL_CLIENT_ID"),
            "client_secret": _require_env("GMAIL_CLIENT_SECRET"),
            "refresh_token": _require_env("GMAIL_REFRESH_TOKEN"),
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    token_response.raise_for_status()
    access_token = str(token_response.json()["access_token"])

    message = MIMEText(html_body, "html")
    message["To"] = recipient
    message["From"] = _require_env("GMAIL_SENDER_EMAIL")
    message["Subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")

    send_response = requests.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"raw": raw},
        timeout=20,
    )
    send_response.raise_for_status()
    return str(send_response.json()["id"])


agent = Agent(
    name="mail_sending_agent",
    seed=os.environ.get("AGENT_SEED_PHRASE", "mail send agentlahackss"),
    port=int(os.environ.get("MAIL_SENDING_AGENT_PORT", "8001")),
    mailbox=True,
    publish_agent_details=True,
)

chat_protocol = Protocol(spec=chat_protocol_spec)
request_protocol = Protocol()


@chat_protocol.on_message(ChatMessage)
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
        payload = extract_email_request(text)
        recipient = payload.get("recipient", "").strip()
        if not recipient:
            response_text = "Who should I send that to?"
        else:
            subject, html_body = build_html_email(payload)
            send_gmail_message(recipient=recipient, subject=subject, html_body=html_body)
            response_text = f"Done — I sent the email to {recipient}."
    except Exception:  # noqa: BLE001
        ctx.logger.exception("Error handling email request")
        response_text = "I couldn't send that email right now."

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


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    return None


@request_protocol.on_message(MailSendingRequest, replies={MailSendingResponse, ErrorMessage})
async def handle_mail_sending_request(ctx: Context, sender: str, msg: MailSendingRequest):
    try:
        payload = extract_email_request(msg.prompt)
        recipient = payload.get("recipient", "").strip()
        if not recipient:
            await ctx.send(sender, ErrorMessage(error="Recipient is required to send the email."))
            return

        subject, html_body = build_html_email(payload)
        message_id = send_gmail_message(recipient=recipient, subject=subject, html_body=html_body)
        await ctx.send(
            sender,
            MailSendingResponse(
                recipient=recipient,
                subject=subject,
                message_id=message_id,
                status="Email sent successfully.",
            ),
        )
    except Exception:  # noqa: BLE001
        ctx.logger.exception("Error handling structured mail sending request")
        await ctx.send(
            sender,
            ErrorMessage(error="An error occurred while processing the email request."),
        )


agent.include(chat_protocol, publish_manifest=True)
agent.include(request_protocol, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
