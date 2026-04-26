# OmegaClaw Backend Channel Runbook

For **real OmegaClaw-Core in Docker** talking to this FastAPI process over HTTP, see [omegaclaw_bridge_runbook.md](omegaclaw_bridge_runbook.md) and [OMEGACLAW_DOCKER_WORKFLOW.md](OMEGACLAW_DOCKER_WORKFLOW.md).

This runbook explains how the **in-process Python shim** channel starts, what configuration it needs, and how it plugs into the local `omegaclaw/` tree and the Agentverse dispatch path.

## Scope

This applies to the OmegaClaw integration under:

- `omegaclaw/channels/my_backend.py`
- `omegaclaw/channels/backend_channel.py`
- `omegaclaw/src/channels.metta`
- `omegaclaw/runtime_loop.py`
- `omegaclaw/remote/agentverse_bridge.py`

## Channel contract (Tutorial 04 shape)

The first-class backend channel adapter is:

- `omegaclaw/channels/my_backend.py`

Contract methods:

- `start_my_backend(backend_url, auth_secret, poll_interval_ms)`
- `getLastMessage()`
- `send_message(str)`

Backend inbox/listener model:

- backend submits a task via `enqueue_message(...)`
- the loop reads via `getLastMessage()`
- the loop responds via `send_message(...)`
- pending backend callers are resolved by `request_id` correlation

## MeTTa wiring (`src/channels.metta`)

Runtime params declared:

- `(= (MY_BACKEND_URL) (empty))`
- `(= (MY_BACKEND_SECRET) (empty))`
- `(= (MY_BACKEND_POLL_MS) (empty))`

Dispatch hooks:

- `(initChannels)` -> `my_backend.start_my_backend(...)` when `commchannel == my_backend`
- `(receive)` -> `my_backend.getLastMessage`
- `(send $msg)` -> `my_backend.send_message`

Required channel selection:

```metta
(configure commchannel my_backend)
(configure MY_BACKEND_URL "ws://localhost:8000/session")
(configure MY_BACKEND_SECRET "dev-secret-or-empty")
(configure MY_BACKEND_POLL_MS 50)
```

## Startup behavior and modes

### Mode A: Local channel-loop mode (default when `OMEGACLAW_URL` is not set)

1. FastAPI session path creates a `GlassesTask`
2. `BackendChannel.submit(...)` enqueues the task into `my_backend`
3. `OmegaClawAgentLoop.run_once()` consumes from channel inbox
4. Loop classifies skill and calls `invoke_remote_skill(...)`
5. Result returns through `send_message(...)` to waiting backend future

### Mode B: Gateway passthrough mode (`OMEGACLAW_URL` is set)

1. `BackendChannel.submit(...)` sends task to `OMEGACLAW_URL/v1/chat/completions`
2. Response is normalized to backend result shape
3. Local channel-loop path is intentionally bypassed

## Required environment/config parameters

Channel + backend:

- `OMEGACLAW_URL` (optional, enables gateway passthrough mode)
- `BACKEND_CHANNEL_URL` (channel runtime param)
- `BACKEND_CHANNEL_SECRET` (channel runtime param)
- `BACKEND_CHANNEL_POLL_MS` (channel runtime param)
- `OMEGACLAW_REQUEST_TIMEOUT_S` (await timeout for channel-loop response)

Remote Agentverse bridge:

- `AGENTVERSE_SKILL_URL` (base URL for remote skill endpoints)
- `SKILL_TIMEOUT_S`
- `SKILL_MAX_RETRIES`

## Agentverse flow linkage (Tutorial 06 shape)

Local skill surface -> Python bridge -> remote agent:

- MeTTa skill lines in `omegaclaw/src/skills.metta`
- Python bridge calls in `omegaclaw/remote/agentverse_bridge.py`
- skill metadata from `omegaclaw/skills/*.json`

Current wrappers include:

- `invoke_identify_person(...)`
- `invoke_describe_scene(...)`
- `invoke_google_search(...)`
- `invoke_google_calendar(...)`
- `invoke_gmail(...)`

## Local developer setup

1. Install backend deps:

```bash
cd backend
uv sync
```

2. Set env (example):

```bash
export AGENTVERSE_SKILL_URL=http://localhost:8001
export SKILL_TIMEOUT_S=5.0
export SKILL_MAX_RETRIES=2
```

3. Start backend:

```bash
uv run uvicorn main:app --reload --port 8000
```

4. Connect iOS app and trigger a skill request.

5. Verify:
- channel loop mode runs when `OMEGACLAW_URL` is unset
- gateway mode runs when `OMEGACLAW_URL` is set
- responses return through the same backend session flow

## Troubleshooting quick checks

- If no response returns: confirm `request_id` reaches `send_message(...)`.
- If remote calls fail: verify `AGENTVERSE_SKILL_URL` and endpoint path.
- If wrong dispatch path: verify whether `OMEGACLAW_URL` is set/unset.
- If MeTTa channel branch is inactive: verify `commchannel` is `my_backend`.
