import asyncio
import json
import logging
import os
from pathlib import Path
import httpx

log = logging.getLogger(__name__)

AGENTVERSE_SKILL_URL = os.environ.get("AGENTVERSE_SKILL_URL", "http://localhost:8001")
SKILL_TIMEOUT_S = float(os.environ.get("SKILL_TIMEOUT_S", "5.0"))
MAX_RETRIES = int(os.environ.get("SKILL_MAX_RETRIES", "2"))

_SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"


def load_skill_config(skill_name: str) -> dict:
    config_path = _SKILLS_DIR / f"{skill_name}.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


async def invoke_remote_skill(skill_name: str, args: dict) -> dict:
    cfg = load_skill_config(skill_name)
    endpoint = cfg.get("endpoint")
    if endpoint:
        url = endpoint
        payload = {"args": args, "agent_address": cfg.get("agent_address", "")}
    elif skill_name == "identify_person":
        url = f"{AGENTVERSE_SKILL_URL}/v1/chat/completions"
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Identify person: "
                        f"{args.get('name', '')}, {args.get('organization', '')}, {args.get('title', '')}"
                    ),
                }
            ],
            "agent_address": cfg.get("agent_address", ""),
        }
    elif skill_name == "describe_scene":
        url = f"{AGENTVERSE_SKILL_URL}/v1/describe"
        payload = {
            "image_context": args.get("image_context", ""),
            "agent_address": cfg.get("agent_address", ""),
        }
    else:
        return _fallback_response(skill_name, "unsupported_skill")

    return await _invoke_with_retry(url, payload, skill_name)


async def invoke_identify_person(name: str, org: str, title: str) -> dict:
    return await invoke_remote_skill(
        "identify_person",
        {"name": name, "organization": org, "title": title},
    )


async def invoke_describe_scene(image_context: str) -> dict:
    return await invoke_remote_skill("describe_scene", {"image_context": image_context})

async def invoke_google_search(query: str) -> dict:
    return await invoke_remote_skill("google_search", {"query": query})


async def invoke_google_calendar(command: str, datetime: str, details: str) -> dict:
    return await invoke_remote_skill(
        "google_calendar",
        {"command": command, "datetime": datetime, "details": details},
    )


async def invoke_gmail(command: str, recipient: str, subject: str, body: str) -> dict:
    return await invoke_remote_skill(
        "gmail",
        {"command": command, "recipient": recipient, "subject": subject, "body": body},
    )


async def _invoke_with_retry(url: str, payload: dict, skill_name: str) -> dict:
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=SKILL_TIMEOUT_S) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, dict) and "choices" in data:
                    return {"summary": data["choices"][0]["message"]["content"], "confidence": "high", "source": f"agentverse:{skill_name}"}
                if isinstance(data, dict):
                    return {**data, "source": f"agentverse:{skill_name}"}
                return {"summary": str(data), "confidence": "low", "source": f"agentverse:{skill_name}"}
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
    if skill_name == "google_search":
        return {"summary": "I could not run Google search right now.", "confidence": "low", "source": "fallback", "error": error}
    if skill_name == "google_calendar":
        return {"summary": "I could not access Google Calendar right now.", "confidence": "low", "source": "fallback", "error": error}
    if skill_name == "gmail":
        return {"summary": "I could not access Gmail right now.", "confidence": "low", "source": "fallback", "error": error}
    return {"description": "I could not describe the scene right now.", "confidence": "low", "source": "fallback", "error": error}
