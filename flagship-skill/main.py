from __future__ import annotations

from fastapi import FastAPI

from people_finder.harness import PeopleFinderHarness
from people_finder.models import IdentifyPersonRequest, IdentifyPersonResponse
from people_finder.settings import Settings

settings = Settings()
harness = PeopleFinderHarness(settings)

app = FastAPI(title="identify_person Agentverse Bridge")


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "agent": settings.person_agent_name,
        "apollo_configured": settings.apollo_configured,
        "asi_configured": settings.asi_configured,
    }


@app.get("/metadata")
def metadata() -> dict[str, object]:
    return {
        "skill_name": "identify_person",
        "skill_type": "inform",
        "description": "Identify a badge wearer using Apollo people and organization search results.",
        "trigger_phrases": [
            "who is this",
            "identify this person",
            "who am I looking at",
            "tell me about this person",
        ],
        "input_schema": {
            "name": "string",
            "organization": "string",
            "title": "string",
            "domain": "string",
            "location": "string",
        },
        "output_schema": {
            "summary": "string",
            "confidence": "high | medium | low",
            "source": "string",
        },
    }


@app.post("/identify_person", response_model=IdentifyPersonResponse)
async def identify_person(request: IdentifyPersonRequest) -> IdentifyPersonResponse:
    if request.max_results == 3:
        request = request.model_copy(update={"max_results": settings.max_tool_results})
    return await harness.identify(request)
