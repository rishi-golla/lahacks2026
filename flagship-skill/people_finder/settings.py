from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Runtime settings loaded from environment variables."""

    asi_one_api_key: str | None = None
    asi_one_base_url: str = "https://api.asi1.ai/v1"
    asi_one_model: str = "asi1"
    asi_one_timeout_seconds: float = 10.0
    model_max_tokens: int = 700

    apollo_api_key: str | None = None
    apollo_base_url: str = "https://api.apollo.io"
    apollo_auth_mode: Literal["x-api-key", "bearer"] = Field(
        default="x-api-key",
    )
    apollo_timeout_seconds: float = 8.0

    person_agent_name: str = "identify-person-agent"
    person_agent_seed: str | None = None
    person_agent_port: int = 8001
    person_agent_mailbox: bool = True
    publish_agent_details: bool = True

    identify_person_agent_address: str | None = None
    bridge_port: int = 8003
    max_tool_results: int = Field(default=3, ge=1, le=10)

    def __init__(self, **data: object):
        loaded = _settings_from_env()
        loaded.update(data)
        super().__init__(**loaded)

    @property
    def apollo_configured(self) -> bool:
        return bool(self.apollo_api_key)

    @property
    def asi_configured(self) -> bool:
        return bool(self.asi_one_api_key)


ENV_MAP = {
    "asi_one_api_key": "ASI_ONE_API_KEY",
    "asi_one_base_url": "ASI_ONE_BASE_URL",
    "asi_one_model": "ASI_ONE_MODEL",
    "asi_one_timeout_seconds": "ASI_ONE_TIMEOUT_SECONDS",
    "model_max_tokens": "MODEL_MAX_TOKENS",
    "apollo_api_key": "APOLLO_API_KEY",
    "apollo_base_url": "APOLLO_BASE_URL",
    "apollo_auth_mode": "APOLLO_AUTH_MODE",
    "apollo_timeout_seconds": "APOLLO_TIMEOUT_SECONDS",
    "person_agent_name": "PERSON_AGENT_NAME",
    "person_agent_seed": "PERSON_AGENT_SEED",
    "person_agent_port": "PERSON_AGENT_PORT",
    "person_agent_mailbox": "PERSON_AGENT_MAILBOX",
    "publish_agent_details": "PUBLISH_AGENT_DETAILS",
    "identify_person_agent_address": "IDENTIFY_PERSON_AGENT_ADDRESS",
    "bridge_port": "BRIDGE_PORT",
    "max_tool_results": "MAX_TOOL_RESULTS",
}

CASTERS = {
    "asi_one_timeout_seconds": float,
    "model_max_tokens": int,
    "apollo_timeout_seconds": float,
    "person_agent_port": int,
    "person_agent_mailbox": lambda value: _as_bool(value),
    "publish_agent_details": lambda value: _as_bool(value),
    "bridge_port": int,
    "max_tool_results": int,
}


def _settings_from_env() -> dict[str, object]:
    env = _load_dotenv()
    env.update(os.environ)

    settings: dict[str, object] = {}
    for field_name, env_name in ENV_MAP.items():
        raw = env.get(env_name)
        if raw is None or raw == "":
            continue
        caster = CASTERS.get(field_name, str)
        settings[field_name] = caster(raw)
    return settings


def _load_dotenv() -> dict[str, str]:
    package_root = Path(__file__).resolve().parents[1]
    candidates = []
    for path in [package_root / ".env", Path.cwd() / ".env"]:
        if path not in candidates:
            candidates.append(path)

    values: dict[str, str] = {}
    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
