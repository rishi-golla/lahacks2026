from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from .apollo import ApolloClient, ApolloError
from .models import IdentifyPersonRequest, ToolBundle, ToolResult


class Tool(Protocol):
    name: str

    async def run(self, request: IdentifyPersonRequest, state: "ToolState") -> ToolResult:
        ...


@dataclass
class ToolState:
    organization_ids: list[str]


class ApolloOrganizationSearchTool:
    name = "apollo.organization_search"

    def __init__(self, client: ApolloClient):
        self._client = client

    async def run(self, request: IdentifyPersonRequest, state: ToolState) -> ToolResult:
        started = time.perf_counter()
        try:
            organizations = await self._client.search_organizations(request)
            state.organization_ids = [organization.id for organization in organizations if organization.id]
            return ToolResult(
                tool_name=self.name,
                ok=True,
                duration_ms=_elapsed_ms(started),
                data=[organization.model_dump(exclude_none=True) for organization in organizations],
            )
        except ApolloError as exc:
            return ToolResult(tool_name=self.name, ok=False, duration_ms=_elapsed_ms(started), error=str(exc))


class ApolloPeopleSearchTool:
    name = "apollo.people_search"

    def __init__(self, client: ApolloClient):
        self._client = client

    async def run(self, request: IdentifyPersonRequest, state: ToolState) -> ToolResult:
        started = time.perf_counter()
        try:
            people = await self._client.search_people(request, organization_ids=state.organization_ids)
            return ToolResult(
                tool_name=self.name,
                ok=True,
                duration_ms=_elapsed_ms(started),
                data=[person.model_dump(exclude_none=True) for person in people],
            )
        except ApolloError as exc:
            return ToolResult(tool_name=self.name, ok=False, duration_ms=_elapsed_ms(started), error=str(exc))


class ApolloToolRunner:
    """Runs data-fetching tools before the response model is called."""

    def __init__(self, client: ApolloClient):
        self._organization_tool = ApolloOrganizationSearchTool(client)
        self._people_tool = ApolloPeopleSearchTool(client)

    async def run(self, request: IdentifyPersonRequest) -> ToolBundle:
        state = ToolState(organization_ids=[])
        results: list[ToolResult] = []

        if request.organization or request.domain:
            results.append(await self._organization_tool.run(request, state))

        results.append(await self._people_tool.run(request, state))

        organization_data = next(
            (result.data for result in results if result.tool_name == self._organization_tool.name and result.ok),
            [],
        )
        people_data = next(
            (result.data for result in results if result.tool_name == self._people_tool.name and result.ok),
            [],
        )

        from .models import OrganizationResult, PersonResult

        return ToolBundle(
            organizations=[OrganizationResult(**item) for item in organization_data],
            people=[PersonResult(**item) for item in people_data],
            tool_results=results,
        )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
