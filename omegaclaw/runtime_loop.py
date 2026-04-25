"""Single-loop OmegaClaw dispatcher for backend channel messages."""

from __future__ import annotations

import json
from typing import Any

from .channels import my_backend
from .remote.agentverse_bridge import invoke_remote_skill


class OmegaClawAgentLoop:
    """Processes channel messages through one dispatch loop."""

    async def run_once(self) -> bool:
        message = my_backend.getLastMessage()
        if message is None:
            return False

        request_id = str(message.get("request_id", ""))
        intent = str(message.get("intent", ""))
        args = message.get("args", {})
        if not isinstance(args, dict):
            args = {}

        skill_name = str(message.get("skill_name") or self._classify(intent, args))
        if skill_name == "unknown":
            result = {
                "summary": "I don't have a matching skill for that request yet.",
                "confidence": "low",
                "source": "omegaclaw:no_match",
            }
        else:
            result = await invoke_remote_skill(skill_name=skill_name, args=args)

        my_backend.send_message(
            json.dumps(
                {
                    "request_id": request_id,
                    "skill_name": skill_name,
                    "result": result,
                }
            )
        )
        return True

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
        return "unknown"
