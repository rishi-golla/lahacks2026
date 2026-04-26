# OmegaClaw HTTP bridge runbook

This connects **real** OmegaClaw-Core (Docker) to the **FastAPI** backend used by the Gemini `agent` tool.

## Components

| Piece | Role |
|-------|------|
| [`channels/lahacks_http.py`](../../PeTTa/repos/OmegaClaw-Core/channels/lahacks_http.py) | Background thread long-polls `GET /internal/omegaclaw/next`; `getLastMessage` / `send_message` for MeTTa |
| [`src/channels.metta`](../../PeTTa/repos/OmegaClaw-Core/src/channels.metta) | `commchannel=lahacks_http` wiring |
| [`backend/app/omegaclaw_bridge.py`](../backend/app/omegaclaw_bridge.py) | In-process queue + Futures |
| [`backend/app/routers/omegaclaw_bridge.py`](../backend/app/routers/omegaclaw_bridge.py) | HTTP routes mounted at `/internal/omegaclaw` |
| [`omegaclaw/channels/backend_channel.py`](../omegaclaw/channels/backend_channel.py) | When `OMEGACLAW_BRIDGE_ENABLED=1`, `submit()` uses `enqueue_and_wait` instead of the Python shim loop |

## Environment

**Backend**

- `OMEGACLAW_BRIDGE_ENABLED=1` — enable routes + `BackendChannel` bridge mode.
- `OMEGACLAW_BRIDGE_SECRET` — optional; if set, require `Authorization: Bearer <secret>` on `/internal/omegaclaw/*` and configure the same value in the OmegaClaw container (`LAHACKS_BRIDGE_SECRET` / script prompts).

**OmegaClaw container**

- Run `./scripts/omegaclaw <your-image>` and choose **option 3** (HTTP bridge).
- Defaults assume the backend at `http://host.docker.internal:8000` (Mac/Windows). On Linux the script adds `--add-host=host.docker.internal:host-gateway` to `docker run`.
- The wrapper passes true Docker runtime options (`-e LAHACKS_*`, Linux `--add-host`) before the image, then passes MeTTa overrides (`commchannel=lahacks_http`, `LAHACKS_*`, provider settings) after the image so `configure` / `argk` sees them.

## Protocol

1. **GET** `/internal/omegaclaw/next` — blocks up to ~55s until a `GlassesTask` is queued by `BackendChannel.submit`. Returns either empty body (idle) or one line: `LAHACKS_TASK_JSON:` + compact JSON (`request_id`, `session_id`, `intent`, `args`, …).
2. OmegaClaw’s LLM runs skills; final user reply should be a **`(send "...")`** whose string is JSON containing at least `request_id` and `result` (`summary`, `confidence`, `source`).
3. **POST** `/internal/omegaclaw/result` with JSON `{"request_id":"…","text":"<string passed to send>"}` — unblocks the waiting `agent` tool call.

## Priority in `BackendChannel.submit`

1. Bridge mode (`OMEGACLAW_BRIDGE_ENABLED`)
2. `OMEGACLAW_URL` (OpenAI-compatible **chat** passthrough — not real MeTTa; legacy)
3. In-process `OmegaClawAgentLoop` + `my_backend` (unit tests / local shims)

## Manual smoke test (you can run)

1. `cd backend && OMEGACLAW_BRIDGE_ENABLED=1 uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`
2. In another terminal: `curl -N "http://127.0.0.1:8000/internal/omegaclaw/next"` (should hang).
3. Trigger any code path that calls `BackendChannel.submit` with bridge enabled, or run `uv run python -m pytest backend/tests/test_omegaclaw_bridge_http.py -q` if present.
4. Build and run real OmegaClaw only after the backend round-trip test passes: `cd PeTTa/repos/OmegaClaw-Core && docker build -t my-omegaclaw:dev . && ./scripts/omegaclaw my-omegaclaw:dev`.

See [OMEGACLAW_DOCKER_WORKFLOW.md](OMEGACLAW_DOCKER_WORKFLOW.md) for clone / build / run order.
