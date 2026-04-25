# OmegaClaw Integration Touch Points

This documents the exact integration seams used to satisfy the PRD channel + remote-skill contract.

## Channel adapter contract (Tutorial 04 shape)

- `omegaclaw/channels/my_backend.py`
  - `start_my_backend(backend_url, auth_secret, poll_interval_ms)`
  - `getLastMessage()`
  - `send_message(text)`
  - backend helper: `enqueue_message(...)` for request/response correlation

## MeTTa channel wiring

- `omegaclaw/src/channels.metta`
  - adds runtime params:
    - `(= (MY_BACKEND_URL) (empty))`
    - `(= (MY_BACKEND_SECRET) (empty))`
    - `(= (MY_BACKEND_POLL_MS) (empty))`
  - wires:
    - `(initChannels)` -> `my_backend.start_my_backend(...)`
    - `(receive)` -> `my_backend.getLastMessage`
    - `(send $msg)` -> `my_backend.send_message`

### Required MeTTa configuration to select backend channel

Set these values before `initChannels` runs:

```metta
(configure commchannel my_backend)
(configure MY_BACKEND_URL "ws://localhost:8000/session")
(configure MY_BACKEND_SECRET "dev-secret-or-empty")
(configure MY_BACKEND_POLL_MS 50)
```

Selection behavior:

- `commchannel = my_backend` enables the backend channel branch in `initChannels`, `receive`, and `send`.
- if `commchannel` is not `my_backend`, backend channel hooks are not used.

## Single-loop dispatch path

- `omegaclaw/runtime_loop.py`
  - `OmegaClawAgentLoop.run_once()`:
    1. reads channel input via `getLastMessage()`
    2. classifies / resolves skill
    3. dispatches through Agentverse bridge
    4. returns response through `send_message(...)`

- `omegaclaw/channels/backend_channel.py`
  - `BackendChannel.submit(GlassesTask)` enqueues one message and lets `OmegaClawAgentLoop` process it.
  - avoids creating a second orchestration loop in backend session code.

## Remote skill dispatch pattern (Tutorial 06 shape)

- `omegaclaw/remote/agentverse_bridge.py`
  - `invoke_remote_skill(skill_name, args)` (generic remote bridge)
  - wrappers:
    - `invoke_identify_person(...)`
    - `invoke_describe_scene(...)`
  - reads per-skill metadata from:
    - `omegaclaw/skills/identify_person.json`
    - `omegaclaw/skills/describe_scene.json`
  - adds retry + timeout + fallback behavior for bridge failures.

## Runtime parameters in use

- `OMEGACLAW_URL` (optional gateway path; bypasses local loop when set)
- `BACKEND_CHANNEL_URL` (channel param)
- `BACKEND_CHANNEL_SECRET` (channel param)
- `BACKEND_CHANNEL_POLL_MS` (channel param)
- `OMEGACLAW_REQUEST_TIMEOUT_S` (wait for loop result)
- `AGENTVERSE_SKILL_URL` (remote bridge target)
- `SKILL_TIMEOUT_S`, `SKILL_MAX_RETRIES` (remote bridge controls)
