# Local skill shims for development without a live OmegaClaw gateway.
# Each shim calls the Agentverse FastAPI service directly.

import os
import httpx
from omegaclaw.channels.backend_channel import GlassesTask

AGENTVERSE_URL = os.environ.get("AGENTVERSE_URL", "http://localhost:8001")

async def dispatch_skill(task: GlassesTask) -> dict:
    skill = _classify(task.intent, task.args)
    if skill == "identify_person":
        return await _identify_person(task.args)
    elif skill == "describe_scene":
        return await _describe_scene(task.args)
    else:
        return {"summary": f"I don't have a skill for that yet.", "confidence": "low", "source": "no-match"}

def _classify(intent: str, args: dict) -> str:
    intent_lower = intent.lower()
    if any(p in intent_lower for p in ["who is", "identify", "who am i looking at", "tell me about this person"]):
        return "identify_person"
    if any(p in intent_lower for p in ["what am i", "describe", "what is this", "what do i see"]):
        return "describe_scene"
    if args.get("name"):
        return "identify_person"
    return "unknown"

async def _identify_person(args: dict) -> dict:
    payload = {
        "messages": [{"role": "user", "content": f"Identify person: {args.get('name', 'Unknown')}, {args.get('organization', 'Unknown')}, {args.get('title', '')}"}]
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{AGENTVERSE_URL}/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return {"summary": data["choices"][0]["message"]["content"], "confidence": "high", "source": "agentverse"}
    except Exception as e:
        return {"summary": f"Could not reach the skill service: {e}", "confidence": "low", "source": "error"}

async def _describe_scene(args: dict) -> dict:
    image_context = args.get("image_context", "")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{AGENTVERSE_URL}/v1/describe", json={"image_context": image_context})
            resp.raise_for_status()
            data = resp.json()
            return {"summary": data.get("description", ""), "confidence": data.get("confidence", "low"), "source": "agentverse"}
    except Exception as e:
        return {"summary": f"Could not reach the scene description service: {e}", "confidence": "low", "source": "error"}
