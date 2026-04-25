# OmegaClaw Integration Touch Points

Repo-grounded verification note for PRD Sections 6, 9, 17, and 18.1.
This captures the exact OmegaClaw-Core extension seams currently used by this repo.

## Verified against OmegaClaw-Core docs

- Tutorial 04 (adding a channel): backend channel adapter contract and MeTTa dispatch hooks
- Tutorial 06 (remote Agentverse skills): local skill surface delegates to Python bridge which calls remote Agentverse skill
- Reference channels + extension points: channel selection via `commchannel`, adapter startup in `initChannels`, and channel read/write via `receive`/`send`

## PRD Assumptions -> Repo Touch Points

| PRD assumption | Actual implementation in repo |
|---|---|
| Custom backend channel adapter in `channels/` | `omegaclaw/channels/my_backend.py` |
| Adapter contract exposes `start_<name>`, `getLastMessage`, `send_message` | `start_my_backend`, `getLastMessage`, `send_message` in `my_backend.py` |
| MeTTa dispatch in `src/channels.metta` | `omegaclaw/src/channels.metta` defines `initChannels`, `receive`, `send` branches |
| Runtime parameter declaration via `(= (MY_*) (empty))` | `MY_BACKEND_URL`, `MY_BACKEND_SECRET`, `MY_BACKEND_POLL_MS` |
| Remote Agentverse path uses local skill -> Python bridge -> remote request | `omegaclaw/src/skills.metta` + `omegaclaw/remote/agentverse_bridge.py` |
| Keep one agent loop (no second competing orchestration loop) | `omegaclaw/runtime_loop.py` + `omegaclaw/channels/backend_channel.py` |

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

## Startup selection behavior

There are two supported startup modes:

1. **Channel-loop mode (default local path)**
   - backend submits `GlassesTask` via `BackendChannel.submit(...)`
   - message is enqueued through `my_backend.enqueue_message(...)`
   - `OmegaClawAgentLoop.run_once()` consumes and dispatches through standard channel path

2. **Gateway passthrough mode**
   - if `OMEGACLAW_URL` is set, `BackendChannel.submit(...)` posts directly to gateway `/v1/chat/completions`
   - this bypasses local loop dispatch intentionally for remote gateway operation

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
    - `invoke_google_search(...)`
    - `invoke_google_calendar(...)`
    - `invoke_gmail(...)`
  - reads per-skill metadata from:
    - `omegaclaw/skills/identify_person.json`
    - `omegaclaw/skills/describe_scene.json`
    - `omegaclaw/skills/google_search.json`
    - `omegaclaw/skills/google_calendar.json`
    - `omegaclaw/skills/gmail.json`
  - adds retry + timeout + fallback behavior for bridge failures.

- `omegaclaw/src/skills.metta`
  - provides LLM-visible descriptive skill lines via `getSkills`
  - provides one-line MeTTa skill surfaces using `py-call (agentverse_bridge.*)`

## Runtime parameters in use

- `OMEGACLAW_URL` (optional gateway path; bypasses local loop when set)
- `BACKEND_CHANNEL_URL` (channel param)
- `BACKEND_CHANNEL_SECRET` (channel param)
- `BACKEND_CHANNEL_POLL_MS` (channel param)
- `OMEGACLAW_REQUEST_TIMEOUT_S` (wait for loop result)
- `AGENTVERSE_SKILL_URL` (remote bridge target)
- `SKILL_TIMEOUT_S`, `SKILL_MAX_RETRIES` (remote bridge controls)

## Verification status

This repo now has one concrete, inspectable integration path for:

- channel adapter contract
- MeTTa channel dispatch wiring
- remote Agentverse bridge
- runtime config + startup selection behavior

That is the exact touch-point set required by issue #13.
