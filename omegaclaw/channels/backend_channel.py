# OmegaClaw channel adapter for the MetaGlasses backend.
# Receives task context from the FastAPI session coordinator and routes
# to OmegaClaw's main agent loop.

from dataclasses import dataclass
from typing import Any

@dataclass
class GlassesTask:
    session_id: str
    turn_id: str
    intent: str          # natural language task from Gemini
    tool_call_id: str    # from Gemini's tool call
    args: dict[str, Any] # extracted args (name, org, title, etc.)
    image_b64: str | None = None  # JPEG if a photo was taken

class BackendChannel:
    """Receives GlassesTask from the session coordinator and dispatches to OmegaClaw."""

    async def submit(self, task: GlassesTask) -> dict[str, Any]:
        """
        Route the task to OmegaClaw and return the result dict.
        In production: calls the OmegaClaw gateway endpoint.
        In stub mode (no OMEGACLAW_URL env): dispatches directly to local skill shims.
        """
        import os
        omegaclaw_url = os.environ.get("OMEGACLAW_URL")
        if omegaclaw_url:
            return await self._call_omegaclaw(omegaclaw_url, task)
        else:
            return await self._local_shim(task)

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

    async def _local_shim(self, task: GlassesTask) -> dict[str, Any]:
        from omegaclaw.skills.shims import dispatch_skill
        return await dispatch_skill(task)
