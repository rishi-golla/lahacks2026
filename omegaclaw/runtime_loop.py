"""Single-loop OmegaClaw dispatcher for backend channel messages."""

from __future__ import annotations

import json
from typing import Any

from .channels import my_backend
from .protocol import make_loop_response, new_tool_call_id
from .remote.agentverse_bridge import invoke_remote_skill
from .skills.shims import invoke_local_skill_shim


class OmegaClawAgentLoop:
    """Processes channel messages through one dispatch loop."""

    _KNOWN_SKILLS = {
        "identify_person",
        "describe_scene",
        "google_search",
        "google_calendar",
        "google_tasks",
        "gmail",
        "people_search_agent",
        "mail_sending_agent",
        "task_scheduling_agent",
        "reminder_agent",
        "purchase_agent",
    }

    async def run_once(self) -> bool:
        message = my_backend.getLastMessage()
        if message is None:
            return False

        request_id = str(message.get("request_id", ""))
        tool_call_id = str(message.get("tool_call_id") or new_tool_call_id())
        intent = str(message.get("intent", ""))
        args = message.get("args", {})
        if not isinstance(args, dict):
            args = {}

        requested_skill_name = str(message.get("skill_name") or "")
        skill_name = requested_skill_name or self._classify(intent, args)
        args = self._normalize_args(skill_name, intent, args)
        if skill_name == "unknown" or (requested_skill_name and skill_name not in self._KNOWN_SKILLS):
            result = {
                "summary": "I don't have a matching skill for that request yet.",
                "confidence": "low",
                "source": "omegaclaw:no_match",
            }
            response = make_loop_response(
                request_id=request_id,
                tool_call_id=tool_call_id,
                skill_name=skill_name,
                result=result,
                args=args,
                error="no_matching_skill",
            )
        else:
            # Reminders use the remote Agentverse agent; identify_person and
            # mail_sending_agent stay on the local shim path.
            if skill_name in {"identify_person", "mail_sending_agent"}:
                result = await invoke_local_skill_shim(skill_name=skill_name, args=args)
            else:
                result = await invoke_remote_skill(skill_name=skill_name, args=args)
            error = result.get("error") if isinstance(result, dict) else None
            response = make_loop_response(
                request_id=request_id,
                tool_call_id=tool_call_id,
                skill_name=skill_name,
                result=result,
                args=args,
                error=str(error) if error else None,
            )

        my_backend.send_message(json.dumps(response))
        return True

    @staticmethod
    def _normalize_args(skill_name: str, intent: str, args: dict[str, Any]) -> dict[str, Any]:
        if skill_name == "reminder_agent" and not any(
            args.get(field) for field in ("command", "datetime", "details")
        ):
            return {
                "command": intent,
                "datetime": "",
                "details": "",
            }
        if skill_name == "mail_sending_agent" and not any(
            args.get(field) for field in ("command", "recipient", "subject", "body")
        ):
            return {
                "command": intent,
                "recipient": "",
                "subject": "",
                "body": "",
            }
        return args

    @staticmethod
    def _classify(intent: str, args: dict[str, Any]) -> str:
        lowered = intent.lower()
        if args.get("name") or any(
            phrase in lowered
            for phrase in ("who is", "identify", "who am i looking at", "tell me about this person")
        ):
            return "identify_person"
        if args.get("image_context") or any(
            phrase in lowered
            for phrase in ("what am i looking at", "describe", "what do i see", "what is this")
        ):
            return "describe_scene"
        if any(phrase in lowered for phrase in ("google", "search for", "look up")):
            return "google_search"
        if any(
            phrase in lowered
            for phrase in (
                "who should i contact",
                "find a person",
                "find this person",
                "people search",
                "look up this person",
            )
        ):
            return "people_search_agent"
        if any(phrase in lowered for phrase in ("calendar", "meeting", "schedule", "event")):
            return "task_scheduling_agent"
        if any(phrase in lowered for phrase in ("task", "todo", "to-do", "remind me", "reminder")):
            if "remind" in lowered or "reminder" in lowered:
                return "reminder_agent"
            return "task_scheduling_agent"
        if any(phrase in lowered for phrase in ("email", "gmail", "send mail", "draft email")):
            return "mail_sending_agent"
        if any(
            phrase in lowered
            for phrase in ("buy", "purchase", "order this", "shop for", "check out")
        ):
            return "purchase_agent"
        return "unknown"
