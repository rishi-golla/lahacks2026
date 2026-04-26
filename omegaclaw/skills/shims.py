"""Local shim entrypoints for OmegaClaw skill dispatch."""

from __future__ import annotations

from typing import Any

from agents.mail_sending_agent import build_html_email, extract_email_request, send_gmail_message
from omegaclaw.remote.agentverse_bridge import invoke_remote_skill


def classify_intent(intent: str, args: dict[str, Any]) -> str:
    intent_lower = intent.lower()
    if any(
        phrase in intent_lower
        for phrase in ("who is", "identify", "who am i looking at", "tell me about this person")
    ):
        return "identify_person"
    if any(phrase in intent_lower for phrase in ("what am i", "describe", "what is this", "what do i see")):
        return "describe_scene"
    if args.get("name"):
        return "identify_person"
    return "unknown"


async def invoke_local_skill_shim(
    *,
    skill_name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Local shim path that delegates to the canonical Agentverse bridge."""
    if skill_name == "unknown":
        return {"summary": "I don't have a skill for that yet.", "confidence": "low", "source": "no-match"}
    if skill_name == "mail_sending_agent":
        return await _invoke_local_mail_sending(args)
    return await invoke_remote_skill(skill_name=skill_name, args=args)

async def _invoke_local_mail_sending(args: dict[str, Any]) -> dict[str, Any]:
    command = str(args.get("command") or "").strip()
    recipient = str(args.get("recipient") or "").strip()
    subject = str(args.get("subject") or "").strip()
    body = str(args.get("body") or "").strip()

    if recipient and (subject or body):
        payload = {
            "recipient": recipient,
            "subject_hint": subject,
            "body_intent": body,
        }
    else:
        payload = extract_email_request(command)
        recipient = str(payload.get("recipient") or "").strip()

    if not recipient:
        return {
            "summary": "Who should I send that to?",
            "confidence": "low",
            "source": "local:mail_sending_agent",
        }

    email_subject, html_body = build_html_email(payload)
    message_id = send_gmail_message(recipient=recipient, subject=email_subject, html_body=html_body)
    return {
        "summary": f"Done - I sent the email to {recipient}.",
        "confidence": "high",
        "source": "local:mail_sending_agent",
        "recipient": recipient,
        "subject": email_subject,
        "message_id": message_id,
    }
async def dispatch_skill(task: Any) -> dict[str, Any]:
    """Compatibility shim for older call sites passing a task-like object."""
    if isinstance(task, dict):
        intent = str(task.get("intent", ""))
        args = task.get("args", {})
    else:
        intent = str(getattr(task, "intent", ""))
        args = getattr(task, "args", {})
    if not isinstance(args, dict):
        args = {}
    skill_name = classify_intent(intent, args)
    return await invoke_local_skill_shim(skill_name=skill_name, args=args)
