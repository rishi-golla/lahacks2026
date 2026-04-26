"""Environment-driven settings for live session adapters."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Resolve `backend/.env` so settings load when the process CWD is not `backend/`.
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class LiveBackend(StrEnum):
    ECHO = "echo"
    GEMINI = "gemini"


class SessionSettings(BaseSettings):
    """Settings used to select and configure the live session backend."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    live_backend: LiveBackend = Field(default=LiveBackend.ECHO, alias="LIVE_BACKEND")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_live_model: str = Field(
        default="gemini-2.5-flash-native-audio-preview-12-2025",
        alias="GEMINI_LIVE_MODEL",
    )
    gemini_api_version: str = Field(default="v1alpha", alias="GEMINI_API_VERSION")
    gemini_response_modalities: Annotated[tuple[str, ...], NoDecode] = Field(
        default=("AUDIO",),
        alias="GEMINI_RESPONSE_MODALITIES",
    )
    session_photo_dump_dir: str | None = Field(default=None, alias="SESSION_PHOTO_DUMP_DIR")

    @field_validator("gemini_response_modalities", mode="before")
    @classmethod
    def normalize_response_modalities(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @model_validator(mode="after")
    def validate_gemini_credentials(self) -> SessionSettings:
        if self.live_backend is LiveBackend.GEMINI and not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when LIVE_BACKEND=gemini")
        return self


def get_session_settings() -> SessionSettings:
    """Load live session settings from the environment and `backend/.env`.

    Intentionally not cached: a cached singleton broke opt-in features toggled
    in `.env` (e.g. `SESSION_PHOTO_DUMP_DIR`) until full process restart, and
    could miss `backend/.env` when the process CWD was not `backend/`.
    """

    return SessionSettings()
