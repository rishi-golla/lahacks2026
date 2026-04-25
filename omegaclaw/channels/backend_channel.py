"""OmegaClaw backend channel entrypoint used by backend session code."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

from omegaclaw.channels import my_backend
from omegaclaw.runtime_loop import OmegaClawAgentLoop


@dataclass
class GlassesTask:
    session_id: str
    turn_id: str
    intent: str          # natural language task from Gemini
    tool_call_id: str    # from Gemini's tool call
    args: dict[str, Any] # extracted args (name, org, title, etc.)
    image_b64: str | None = None  # JPEG if a photo was taken

    def to_channel_message(self) -> dict[str, Any]:
        payload = {
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "intent": self.intent,
            "tool_call_id": self.tool_call_id,
            "args": self.args,
            "skill_name": self.args.get("skill_name"),
        }
        if self.image_b64 is not None:
            payload["image_b64"] = self.image_b64
        return payload

class BackendChannel:
    """Receives GlassesTask from session coordinator and dispatches via channel loop."""

    def __init__(self) -> None:
        self._loop = OmegaClawAgentLoop()
        self._request_timeout_s = float(os.environ.get("OMEGACLAW_REQUEST_TIMEOUT_S", "8.0"))

    async def submit(self, task: GlassesTask) -> dict[str, Any]:
        """Route a task to OmegaClaw and return normalized skill output."""
        omegaclaw_url = os.environ.get("OMEGACLAW_URL")
        if omegaclaw_url:
            return await self._call_omegaclaw(omegaclaw_url, task)
        return await self._dispatch_via_channel_loop(task)

    async def _dispatch_via_channel_loop(self, task: GlassesTask) -> dict[str, Any]:
        my_backend.start_my_backend(
            backend_url=os.environ.get("BACKEND_CHANNEL_URL", ""),
            auth_secret=os.environ.get("BACKEND_CHANNEL_SECRET"),
            poll_interval_ms=int(os.environ.get("BACKEND_CHANNEL_POLL_MS", "50")),
        )
        _request_id, pending = my_backend.enqueue_message(task.to_channel_message())
        # One clean OmegaClaw loop handles intake + remote dispatch.
        await self._loop.run_once()
        response = await asyncio.wait_for(pending, timeout=self._request_timeout_s)
        result = response.get("result")
        if isinstance(result, dict):
            return result
        return {"summary": "Invalid channel response", "confidence": "low", "source": "omegaclaw:channel"}

    async def _call_omegaclaw(self, url: str, task: GlassesTask) -> dict[str, Any]:
        import httpx
        payload = {
            "messages": [{"role": "user", "content": f"Identify person: {task.args.get('name', '')}, {task.args.get('organization', '')}, {task.args.get('title', '')}"}]
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(f"{url}/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return {"summary": data["choices"][0]["message"]["content"], "confidence": "high", "source": "omegaclaw"}
