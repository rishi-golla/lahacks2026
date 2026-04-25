from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Confidence = Literal["high", "medium", "low"]


class IdentifyPersonRequest(BaseModel):
    """Normalized input from badge OCR, OmegaClaw, ASI chat, or the HTTP bridge."""

    name: str | None = None
    organization: str | None = None
    title: str | None = None
    domain: str | None = None
    location: str | None = None
    raw_query: str | None = None
    max_results: int = Field(default=3, ge=1, le=10)

    @field_validator("name", "organization", "title", "domain", "location", "raw_query", mode="before")
    @classmethod
    def blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class OrganizationResult(BaseModel):
    id: str | None = None
    name: str | None = None
    domain: str | None = None
    website_url: str | None = None
    industry: str | None = None
    estimated_num_employees: int | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    short_description: str | None = None

    @classmethod
    def from_apollo(cls, raw: dict[str, Any]) -> "OrganizationResult":
        return cls(
            id=_as_str(raw.get("id") or raw.get("organization_id")),
            name=_as_str(raw.get("name") or raw.get("organization_name")),
            domain=_as_str(raw.get("primary_domain") or raw.get("domain")),
            website_url=_as_str(raw.get("website_url") or raw.get("website")),
            industry=_as_str(raw.get("industry")),
            estimated_num_employees=_as_int(
                raw.get("estimated_num_employees") or raw.get("organization_num_employees")
            ),
            city=_as_str(raw.get("city")),
            state=_as_str(raw.get("state")),
            country=_as_str(raw.get("country")),
            short_description=_as_str(raw.get("short_description") or raw.get("seo_description")),
        )


class PersonResult(BaseModel):
    id: str | None = None
    name: str | None = None
    title: str | None = None
    organization_name: str | None = None
    organization_id: str | None = None
    linkedin_url: str | None = None
    headline: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    score: float = 0.0

    @classmethod
    def from_apollo(cls, raw: dict[str, Any]) -> "PersonResult":
        org = raw.get("organization")
        org = org if isinstance(org, dict) else {}
        first_name = _as_str(raw.get("first_name"))
        last_name = _as_str(raw.get("last_name"))
        full_name = _as_str(raw.get("name"))
        if not full_name:
            full_name = " ".join(part for part in [first_name, last_name] if part) or None

        return cls(
            id=_as_str(raw.get("id")),
            name=full_name,
            title=_as_str(raw.get("title") or raw.get("headline")),
            organization_name=_as_str(
                raw.get("organization_name")
                or raw.get("employer_name")
                or org.get("name")
            ),
            organization_id=_as_str(raw.get("organization_id") or org.get("id")),
            linkedin_url=_as_str(raw.get("linkedin_url")),
            headline=_as_str(raw.get("headline")),
            city=_as_str(raw.get("city")),
            state=_as_str(raw.get("state")),
            country=_as_str(raw.get("country")),
        )


class ToolResult(BaseModel):
    tool_name: str
    ok: bool
    duration_ms: int
    data: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class ToolBundle(BaseModel):
    organizations: list[OrganizationResult] = Field(default_factory=list)
    people: list[PersonResult] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return bool(self.organizations or self.people)


class IdentifyPersonResponse(BaseModel):
    summary: str
    confidence: Confidence
    source: str
    matched_person: PersonResult | None = None
    organizations: list[OrganizationResult] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return str(value)


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
