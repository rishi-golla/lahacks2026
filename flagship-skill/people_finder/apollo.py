from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx

from .models import IdentifyPersonRequest, OrganizationResult, PersonResult
from .settings import Settings


class ApolloError(RuntimeError):
    """Raised when Apollo cannot return usable search data."""


class ApolloNotConfigured(ApolloError):
    """Raised when APOLLO_API_KEY is missing."""


class ApolloClient:
    """Small Apollo REST client for organization and people search tools."""

    PEOPLE_SEARCH_PATH = "/api/v1/mixed_people/api_search"
    ORGANIZATION_SEARCH_PATH = "/api/v1/mixed_companies/search"

    def __init__(self, settings: Settings):
        self._settings = settings

    async def search_organizations(self, request: IdentifyPersonRequest) -> list[OrganizationResult]:
        params: list[tuple[str, str | int | bool]] = [
            ("page", 1),
            ("per_page", request.max_results),
        ]
        if request.organization:
            params.append(("q_organization_name", request.organization))
        if request.domain:
            params.append(("q_organization_domains_list[]", _clean_domain(request.domain)))

        if len(params) == 2:
            return []

        payload = await self._post(self.ORGANIZATION_SEARCH_PATH, params)
        raw_items = _extract_items(payload, "organizations", "companies", "accounts")
        return [OrganizationResult.from_apollo(item) for item in raw_items]

    async def search_people(
        self,
        request: IdentifyPersonRequest,
        organization_ids: Iterable[str] = (),
    ) -> list[PersonResult]:
        params: list[tuple[str, str | int | bool]] = [
            ("page", 1),
            ("per_page", request.max_results),
            ("include_similar_titles", False),
        ]

        if request.title:
            params.append(("person_titles[]", request.title))

        for organization_id in organization_ids:
            params.append(("organization_ids[]", organization_id))

        if not any(key == "organization_ids[]" for key, _ in params) and request.domain:
            params.append(("q_organization_domains_list[]", _clean_domain(request.domain)))

        keyword_parts = [request.name, request.organization]
        if request.raw_query and not request.name:
            keyword_parts.append(request.raw_query)
        q_keywords = " ".join(part for part in keyword_parts if part)
        if q_keywords:
            params.append(("q_keywords", q_keywords))

        if request.location:
            params.append(("person_locations[]", request.location))

        payload = await self._post(self.PEOPLE_SEARCH_PATH, params)
        raw_items = _extract_items(payload, "people", "contacts", "persons")
        people = [PersonResult.from_apollo(item) for item in raw_items]
        return sorted(
            (person.model_copy(update={"score": _score_person(request, person)}) for person in people),
            key=lambda person: person.score,
            reverse=True,
        )

    async def _post(self, path: str, params: list[tuple[str, str | int | bool]]) -> dict[str, Any]:
        if not self._settings.apollo_api_key:
            raise ApolloNotConfigured("APOLLO_API_KEY is not configured")

        headers = self._headers()
        payload = _apollo_json_payload(params)
        async with httpx.AsyncClient(
            base_url=self._settings.apollo_base_url,
            timeout=self._settings.apollo_timeout_seconds,
        ) as client:
            response = await client.post(path, headers=headers, json=payload)

        if response.status_code >= 400:
            detail = response.text[:500]
            raise ApolloError(f"Apollo returned HTTP {response.status_code}: {detail}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise ApolloError("Apollo returned non-JSON response") from exc

        if not isinstance(payload, dict):
            raise ApolloError("Apollo returned unexpected response shape")
        return payload

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "accept": "application/json",
            "Cache-Control": "no-cache",
            "x-api-key": self._settings.apollo_api_key or "",
        }


def _extract_items(payload: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _apollo_json_payload(params: list[tuple[str, str | int | bool]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in params:
        normalized_key = key.removesuffix("[]")
        if key.endswith("[]"):
            existing = payload.setdefault(normalized_key, [])
            if isinstance(existing, list):
                existing.append(value)
            else:
                payload[normalized_key] = [existing, value]
        else:
            payload[normalized_key] = value
    return payload


def _clean_domain(domain: str) -> str:
    domain = domain.strip().lower()
    domain = domain.removeprefix("https://").removeprefix("http://").removeprefix("www.")
    return domain.split("/", 1)[0].strip()


def _score_person(request: IdentifyPersonRequest, person: PersonResult) -> float:
    score = 0.0
    if _contains_all_terms(person.name, request.name):
        score += 0.5
    if _contains_all_terms(person.organization_name, request.organization):
        score += 0.25
    if _contains_any_term(person.title, request.title):
        score += 0.2
    if person.linkedin_url:
        score += 0.05
    return min(score, 1.0)


def _contains_all_terms(value: str | None, target: str | None) -> bool:
    if not value or not target:
        return False
    value_lower = value.lower()
    terms = [part for part in target.lower().replace("-", " ").split() if part]
    return bool(terms) and all(term in value_lower for term in terms)


def _contains_any_term(value: str | None, target: str | None) -> bool:
    if not value or not target:
        return False
    value_lower = value.lower()
    terms = [part for part in target.lower().replace("-", " ").split() if len(part) > 2]
    return bool(terms) and any(term in value_lower for term in terms)
