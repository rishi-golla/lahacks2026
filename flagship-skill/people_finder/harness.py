from __future__ import annotations

from .apollo import ApolloClient
from .model_harness import ResponseModelHarness
from .models import IdentifyPersonRequest, IdentifyPersonResponse, ToolBundle, ToolResult
from .settings import Settings
from .tools import ApolloToolRunner


class PeopleFinderHarness:
    """Coordinates Apollo data tools and ASI:One response generation."""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or Settings()
        self._tool_runner = ApolloToolRunner(ApolloClient(self._settings))
        self._response_model = ResponseModelHarness(self._settings)

    async def identify(self, request: IdentifyPersonRequest) -> IdentifyPersonResponse:
        if not request.name:
            tools = ToolBundle(
                tool_results=[
                    ToolResult(
                        tool_name="input.validation",
                        ok=False,
                        duration_ms=0,
                        error="missing name",
                    )
                ]
            )
            return await self._response_model.formulate(request, tools)

        tools = await self._tool_runner.run(request)
        return await self._response_model.formulate(request, tools)
