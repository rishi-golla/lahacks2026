# ContextLens Agent

A FastAPI + uAgents service that provides person-intelligence and scene-description skills for the ContextLens project.

## Architecture

- **`main.py`** — FastAPI HTTP bridge, exposing OpenAI-compatible and custom endpoints.
- **`agent.py`** — uAgents daemon handling peer-to-peer uAgent messages from Agentverse.
- **`context_service.py`** — Calls Gemini 1.5 Flash to generate spoken-audio summaries of a person's professional role.
- **`describe_service.py`** — Calls Gemini 1.5 Flash to describe a scene from image-context text.
- **`models.py`** — Shared Pydantic models (`PersonQuery`, `PersonContext`).

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes | — | Google Generative AI API key |
| `AGENT_SEED` | No | `contextlens-default-seed-2026` | Deterministic seed for the uAgent address |
| `PORT` | No | `8001` | HTTP port for the FastAPI server |

Copy `.env.example` to `.env` and fill in your key:

```bash
cp .env.example .env
# edit .env and set GEMINI_API_KEY
```

## Local Development Setup

### Prerequisites

- Python 3.11+
- A Google Generative AI API key ([get one here](https://aistudio.google.com/))

### Install dependencies

```bash
cd contextlens-agent
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run the FastAPI server

```bash
python main.py
# Server starts on http://localhost:8001
```

### Run the uAgent daemon

In a separate terminal:

```bash
python agent.py
```

### API Endpoints

#### `GET /health`
```json
{"status": "ok"}
```

#### `POST /v1/chat/completions`
OpenAI-compatible endpoint. OmegaClaw sends task strings here.

Request:
```json
{
  "messages": [
    {"role": "user", "content": "Identify person: Elon Musk, xAI, CEO"}
  ]
}
```

Response:
```json
{
  "choices": [
    {"message": {"role": "assistant", "content": "Elon Musk is the CEO of xAI..."}}
  ]
}
```

#### `POST /v1/describe`
Describe a scene from image context text.

Request:
```json
{"image_context": "A conference room with a whiteboard showing a system architecture diagram."}
```

Response:
```json
{"description": "The scene shows a conference room...", "confidence": "high"}
```

## Running the Smoke Test

```bash
bash scripts/smoke_install.sh
```

This creates a temporary virtualenv, installs all pinned requirements, and verifies imports are working.

## Running the Evaluation Suite

```bash
# From the contextlens-agent directory (with .venv active)
python eval/run_eval.py
```

This runs all cases in `eval/fixtures.json` against `get_person_context` and prints a pass/fail table.

## Registering on Agentverse

1. Install the uAgents SDK and start the agent:
   ```bash
   python agent.py
   ```
   On startup, uAgents prints the agent's address, e.g.:
   ```
   INFO:     [contextlens-person-intelligence]: Starting agent...
   INFO:     [contextlens-person-intelligence]: Agent address: agent1q...
   ```

2. Go to [Agentverse](https://agentverse.ai) and sign in.

3. Click **Register Agent** and paste the agent address printed above.

4. The agent address format is:
   ```
   agent1q<base32-encoded-public-key>
   ```
   It is deterministically derived from `AGENT_SEED`, so the same seed always produces the same address.

5. Set any required metadata (name, description, tags) and publish.

OmegaClaw or other uAgents can then discover and send `PersonQuery` messages to this agent via the Almanac.
