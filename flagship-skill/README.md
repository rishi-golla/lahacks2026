# identify_person Agentverse Skill

ASI:One-compatible people-finding agent for the OmegaClaw glasses runtime.

The agent receives badge context such as `name`, `organization`, and `title`, runs Apollo data-fetching tools, and gives ASI:One the tool results so it can produce a short spoken response. It does not perform facial recognition and does not request Apollo email or phone enrichment.

## Files

- `agent.py` runs the Agentverse uAgent with ASI:One chat protocol support.
- `main.py` runs a local FastAPI bridge for backend/OmegaClaw integration tests.
- `people_finder/apollo.py` contains the Apollo People API Search and Organization Search client.
- `people_finder/tools.py` defines the tool framework.
- `people_finder/model_harness.py` calls ASI:One after tools return data.
- `client.py` smoke-tests either the local bridge or the registered Agentverse agent.

## Setup

```bash
cd flagship-skill
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill in:

```env
ASI_ONE_API_KEY=...
APOLLO_API_KEY=...
PERSON_AGENT_SEED=stable seed phrase here
```

Apollo requests follow the official Python snippet shape: `POST` with `Content-Type: application/json`, `accept: application/json`, `Cache-Control: no-cache`, and `x-api-key`.

## Run The Agentverse Agent

```bash
python agent.py
```

Expected startup checks:

- stable `agent1...` address is printed
- mailbox client starts
- registration succeeds
- `AgentChatProtocol` manifest is published

In Agentverse, set the public profile metadata:

- name: `identify_person`
- handle: `@identify-person`
- description: `Identify a visible badge wearer from badge fields using Apollo people and organization search.`
- tags: `people-search`, `apollo`, `agentverse`, `omegaclaw`, `smart-glasses`

## Run The HTTP Bridge

```bash
fastapi dev main.py --port 8003
```

Smoke test:

```bash
python client.py --mode bridge --name "Angela" --organization "LA Hacks" --title "Organizer"
```

The bridge exposes:

- `GET /health`
- `GET /metadata`
- `POST /identify_person`

Request:

```json
{
  "name": "Angela",
  "organization": "LA Hacks",
  "title": "Organizer",
  "domain": "lahacks.com"
}
```

Response:

```json
{
  "summary": "Angela appears to be an Organizer at LA Hacks.",
  "confidence": "medium",
  "source": "badge fields + apollo.organization_search, apollo.people_search"
}
```

## Agentverse Structured Smoke Test

After the agent is registered, copy its `agent1...` address:

```bash
python client.py --mode agent --address agent1... --seed "client seed phrase" --name "Angela" --organization "LA Hacks" --title "Organizer"
```

The Agentverse smoke client is itself a small uAgent, so stop it with `Ctrl+C` after it logs the reply.

## OmegaClaw Skill Hook

The local OmegaClaw skill should keep the PRD shape:

```metta
"- Identify a visible badge wearer and return short professional context: (identify-person name_in_quotes organization_in_quotes title_in_quotes)"
```

```metta
(= (identify-person $name $organization $title)
   (py-call (agentverse.identify_person $name $organization $title)))
```

The Python bridge function should either:

1. call `POST /identify_person` for local/deployed HTTP bridge testing, or
2. send `IdentifyPersonQuery` to the fixed Agentverse address for prize-track registration.

## QA Checklist

- Missing name returns low confidence and asks for a readable badge.
- Apollo 401/403/429 returns a graceful low-confidence response, not an agent crash.
- No Apollo key returns badge-only fallback.
- No ASI:One key still returns deterministic fallback text.
- ASI:One Chat accepts JSON text payloads and simple phrases like `Who is Angela from LA Hacks?`.
- Response stays short enough for glasses audio.
