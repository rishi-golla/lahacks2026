# Bridge between OmegaClaw and the registered Agentverse uAgent.
# Handles HTTP POST to the Agentverse-registered endpoint with timeout,
# retry, and fallback behavior.

import asyncio
import logging
import os
import httpx

log = logging.getLogger(__name__)

AGENTVERSE_SKILL_URL = os.environ.get("AGENTVERSE_SKILL_URL", "http://localhost:8001")
SKILL_TIMEOUT_S = float(os.environ.get("SKILL_TIMEOUT_S", "5.0"))
MAX_RETRIES = int(os.environ.get("SKILL_MAX_RETRIES", "2"))

async def invoke_identify_person(name: str, org: str, title: str) -> dict:
    payload = {"messages": [{"role": "user", "content": f"Identify person: {name}, {org}, {title}"}]}
    return await _invoke_with_retry(f"{AGENTVERSE_SKILL_URL}/v1/chat/completions", payload, "identify_person")

async def invoke_describe_scene(image_context: str) -> dict:
    return await _invoke_with_retry(f"{AGENTVERSE_SKILL_URL}/v1/describe", {"image_context": image_context}, "describe_scene")

async def _invoke_with_retry(url: str, payload: dict, skill_name: str) -> dict:
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=SKILL_TIMEOUT_S) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                if "choices" in data:
                    return {"summary": data["choices"][0]["message"]["content"], "confidence": "high", "source": f"agentverse:{skill_name}"}
                return {**data, "source": f"agentverse:{skill_name}"}
        except httpx.TimeoutException:
            last_error = f"timeout after {SKILL_TIMEOUT_S}s"
            log.warning("skill_timeout skill=%s attempt=%d", skill_name, attempt + 1)
        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}"
            log.warning("skill_http_error skill=%s status=%d", skill_name, e.response.status_code)
            break
        except Exception as e:
            last_error = str(e)
            log.warning("skill_error skill=%s error=%s", skill_name, e)
        if attempt < MAX_RETRIES:
            await asyncio.sleep(0.2 * (attempt + 1))

    log.error("skill_failed skill=%s error=%s", skill_name, last_error)
    return _fallback_response(skill_name, last_error)

def _fallback_response(skill_name: str, error: str) -> dict:
    if skill_name == "identify_person":
        return {"summary": "I could not find information on that person right now.", "confidence": "low", "source": "fallback", "error": error}
    return {"description": "I could not describe the scene right now.", "confidence": "low", "source": "fallback", "error": error}
