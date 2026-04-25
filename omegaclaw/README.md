# OmegaClaw — Agent Orchestration Layer

OmegaClaw is [Fetch.ai](https://fetch.ai/)'s agent orchestration layer. In this project it sits between the FastAPI backend and Agentverse specialist agents, routing tasks from Meta Ray-Ban glasses sessions to the right skill, handling retries, timeouts, and fallback responses.

---

## Architecture

```
iOS App
  │  WebSocket
  ▼
FastAPI backend  (backend/)
  │  BackendChannel.submit(GlassesTask)
  ▼
OmegaClaw  (omegaclaw/)
  ├── channels/backend_channel.py   ← Tutorial 04: channel adapter
  ├── skills/shims.py               ← local dev dispatch (no gateway needed)
  ├── remote/agentverse_bridge.py   ← Tutorial 06: remote Agentverse uAgent
  └── protocol.py                   ← tool_event formatting for iOS
  │
  ▼
Agentverse uAgents  (specialist skills)
```

### Extension seams used

| OmegaClaw concept | Tutorial | File in this repo |
|---|---|---|
| Channel adapter | Tutorial 04 — Channels | `channels/backend_channel.py` |
| Remote uAgent bridge | Tutorial 06 — Remote agents | `remote/agentverse_bridge.py` |

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `OMEGACLAW_URL` | _(unset)_ | OmegaClaw gateway base URL. If unset, runs in local shim mode. |
| `AGENTVERSE_URL` | `http://localhost:8001` | Agentverse service URL used by local shims. |
| `AGENTVERSE_SKILL_URL` | `http://localhost:8001` | Agentverse skill endpoint used by the remote bridge. |
| `SKILL_TIMEOUT_S` | `5.0` | Per-attempt HTTP timeout for skill calls (seconds). |
| `SKILL_MAX_RETRIES` | `2` | Number of retry attempts on timeout. |

---

## Local developer setup (no OmegaClaw gateway)

When `OMEGACLAW_URL` is **not set**, `BackendChannel.submit()` falls through to the local shim dispatcher in `skills/shims.py`. This lets you develop and test end-to-end without a running OmegaClaw gateway.

1. Clone the repo and install backend dependencies:
   ```bash
   cd backend
   uv sync
   ```

2. Start the backend:
   ```bash
   uv run uvicorn main:app --reload --port 8000
   ```

3. (Optional) Start a mock Agentverse skill service on port 8001, or leave it down — the shims return graceful error summaries if the service is unreachable.

4. Connect the iOS app. All `GlassesTask` objects will be dispatched through `_local_shim` automatically.

---

## Running with the OmegaClaw gateway

Set `OMEGACLAW_URL` to your gateway base URL before starting the backend:

```bash
export OMEGACLAW_URL=https://your-omegaclaw-gateway.example.com
uv run uvicorn main:app --reload --port 8000
```

`BackendChannel._call_omegaclaw` will POST to `{OMEGACLAW_URL}/v1/chat/completions`.

---

## Registering a skill on Agentverse

1. Go to [Agentverse](https://agentverse.ai/) and sign in.
2. Create a new uAgent for your skill (e.g. `identify_person`).
3. Deploy the agent code (see `contextlens-agent/` for reference).
4. Copy the agent address shown in the Agentverse dashboard (format: `agent1q...`).
5. Update the corresponding skill config JSON (see next section).

---

## Updating skill config after registration

After registering on Agentverse, fill in the `agent_address` field in the skill config:

**`omegaclaw/skills/identify_person.json`**
```json
{
  "agent_address": "agent1qABC123..."
}
```

**`omegaclaw/skills/describe_scene.json`**
```json
{
  "agent_address": "agent1qXYZ456..."
}
```

The `agent_address` is used by the remote bridge to route messages to the correct uAgent.

---

## Adding a new skill

1. **Add a shim** in `omegaclaw/skills/shims.py`:
   - Add a new intent pattern to `_classify()`.
   - Add a new `_my_skill(args)` async function that calls the Agentverse endpoint.
   - Add a branch in `dispatch_skill()` to call it.

2. **Add a config JSON** at `omegaclaw/skills/<skill_name>.json` following the schema of `identify_person.json`. Fill in `trigger_phrases`, `input_schema`, and `output_schema`. Leave `agent_address` as the placeholder until you register.

3. **Add a bridge function** in `omegaclaw/remote/agentverse_bridge.py` (e.g. `invoke_my_skill(...)`).

4. **Register on Agentverse** (see above) and fill in the `agent_address`.

5. **Test locally** without setting `OMEGACLAW_URL` — the shim will be invoked directly.
