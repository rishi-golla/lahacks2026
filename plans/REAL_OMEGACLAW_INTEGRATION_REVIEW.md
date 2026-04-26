# Real OmegaClaw Integration Review

**Status:** Updated review plan based on current uncommitted/unstaged code.  
**Last reviewed:** 2026-04-25  
**Original plan reviewed:** `/Users/lucaskim/.cursor/plans/real_omegaclaw_integration_da7d8e94.plan.md`

## Verdict

The original plan's **architecture still makes sense**: keep Gemini's `agent` tool surface, run real OmegaClaw-Core as a long-lived Docker sidecar, bridge backend work into OmegaClaw through a custom channel, and complete requests via OmegaClaw `(send ...)`.

However, the original plan's todo statuses are too optimistic. The current code has most of the scaffolding implemented, but it should be treated as **partially integrated, not end-to-end complete** until the run path and one live bridge smoke test are fixed.

## What is already implemented

### Backend repo

- `backend/app/omegaclaw_bridge.py` implements an in-process async queue and request waiters.
- `backend/app/routers/omegaclaw_bridge.py` exposes:
  - `GET /internal/omegaclaw/next`
  - `POST /internal/omegaclaw/result`
- `backend/app/main.py` mounts the bridge router under `/internal/omegaclaw`.
- `omegaclaw/channels/backend_channel.py` now chooses bridge mode first when `OMEGACLAW_BRIDGE_ENABLED=1`.
- `backend/tests/test_omegaclaw_bridge_http.py` covers basic queue-to-GET and result-to-waiter behavior.
- `backend/app/session/live_adapter.py` already declares the Gemini `agent` tool and routes tool calls through `BackendChannel.submit` when available.

### OmegaClaw-Core tree

- `PeTTa/repos/OmegaClaw-Core` is on `hackathon-2604`.
- `channels/lahacks_http.py` exists and follows the expected channel contract:
  - background HTTP long-poll thread
  - non-blocking consume-on-read `getLastMessage()`
  - `send_message()` posts results back to FastAPI
- `src/channels.metta` declares `LAHACKS_*` config atoms and wires `lahacks_http` into `initChannels`, `receive`, and `send`.
- `lib_omegaclaw.metta` imports the new channel and `src/lahacks_skills.py`.
- `memory/prompt.txt` includes instructions for `LAHACKS_TASK_JSON:` and final JSON `(send ...)`.
- `scripts/omegaclaw` adds an option for the LA Hacks HTTP bridge.
- A deterministic smoke-test skill exists: `lahacks-echo` in `src/skills.metta` backed by `src/lahacks_skills.py`.

## Important discrepancies / risks

### 1. Docker wrapper option placement likely needs fixing

In `PeTTa/repos/OmegaClaw-Core/scripts/omegaclaw`, the base `docker_cmd` currently adds the image and command args before the `lahacks_http` branch appends `-e ...` and `--add-host ...` options.

That means the LAHACKS `-e` flags and Linux `--add-host` may be passed as container command arguments instead of Docker options. The LAHACKS key/value arguments might still be visible to MeTTa's `argk`, but this is accidental and the Linux host mapping will not be applied as intended.

**Plan update:** move Docker runtime options before `"$image"`, or intentionally pass LAHACKS values as MeTTa `key=value` args after the image and put only true Docker options before the image.

### 2. Concurrency is not explicitly single-flight

The backend supports multiple waiters keyed by `request_id`, but `channels/lahacks_http.py` stores only one `_last_message` slot. If the backend queues multiple jobs before the MeTTa loop consumes the first, the channel thread can overwrite the pending message.

**Plan update:** choose one explicitly:

- **Hackathon single-flight:** reject or wait when one bridge request is already outstanding.
- **Queue in channel adapter:** replace `_last_message` with a small FIFO queue consumed by `getLastMessage()`.

For demo reliability, single-flight is probably enough and easier to reason about.

### 3. End-to-end live bridge test is still missing

Current tests validate the HTTP queue primitives, but they do not prove the full bridge path:

`BackendChannel.submit()` -> backend queue -> `GET /next` -> OmegaClaw-style result -> `POST /result` -> submit returns normalized result.

**Plan update:** add one integration test or script that runs this exact round trip without Gemini and without a full OmegaClaw container.

### 4. Agentverse skill item is not truly complete

The original plan says to add one Agentverse skill and smoke-test it. Current OmegaClaw-Core changes add `lahacks-echo`, which is useful for deterministic bridge testing but is not an Agentverse/uAgents skill. Stock `tavily-search` and `technical-analysis` exist in `src/agentverse.py`, but there is no new LA Hacks Agentverse-backed skill proven end to end.

**Plan update:** keep `lahacks-echo` as the bridge smoke skill, then separately prove one real Agentverse-backed skill through the bridge.

### 5. Correlation depends on the model obeying the prompt

`complete_from_result()` requires `request_id`, either top-level in the POST body or inside the sent JSON text. The prompt tells OmegaClaw to include it, but if the model emits plain text or omits `request_id`, the waiter times out.

**Plan update:** for hackathon mode, add single-flight fallback or clearer failure logging. For production-shaped mode, keep strict `request_id`.

## Updated implementation plan

### Phase 1 — Make the run path deterministic

1. Fix `scripts/omegaclaw` so Docker options are placed before the image.
2. Decide whether LAHACKS bridge settings are passed as:
   - Docker env vars consumed by `lahacks_http.py`, or
   - MeTTa `key=value` argv consumed by `configure` / `argk`.
3. Verify `commchannel=lahacks_http` actually reaches `src/channels.metta` when choosing option 3.
4. Document the exact backend and container startup commands in `docs/omegaclaw_bridge_runbook.md`.

### Phase 2 — Enforce bridge request semantics

1. Pick **single-flight** for the demo unless concurrent tool calls are required.
2. In backend bridge state, track whether a request is already outstanding.
3. Return a clean fallback result or wait rather than allowing multiple queued jobs to overwrite `_last_message`.
4. Keep `request_id` correlation as the preferred path.

### Phase 3 — Add a real bridge round-trip test

Create a test or script that:

1. Enables `OMEGACLAW_BRIDGE_ENABLED=1`.
2. Starts `BackendChannel.submit()` in the background.
3. Calls `GET /internal/omegaclaw/next` and verifies a `LAHACKS_TASK_JSON:` line with the same `request_id`.
4. Calls `POST /internal/omegaclaw/result` with valid JSON text.
5. Asserts `BackendChannel.submit()` returns the normalized `result`.

This should pass before trying to debug a real Docker/LLM run.

### Phase 4 — Smoke-test real OmegaClaw-Core without Gemini

1. Build the custom OmegaClaw image from `PeTTa/repos/OmegaClaw-Core`.
2. Start FastAPI with `OMEGACLAW_BRIDGE_ENABLED=1`.
3. Run `./scripts/omegaclaw <your-image>` and select LA Hacks HTTP bridge.
4. Inject a task whose intent strongly asks for `lahacks-echo` and a final `(send ...)`.
5. Confirm backend receives a result before timeout.

### Phase 5 — Prove one real skill path

1. First use existing built-in web/Agentverse skill if available, such as `tavily-search`, to avoid adding complexity.
2. Then add or polish one LA Hacks-specific Agentverse skill only if the bridge is stable.
3. Rebuild the OmegaClaw Docker image after every OmegaClaw-Core source change.

### Phase 6 — Demo hardening

1. Keep `OMEGACLAW_URL` documented as legacy OpenAI-compatible chat passthrough, not real OmegaClaw-Core.
2. Keep in-process `OmegaClawAgentLoop` as a fallback/test shim only.
3. Keep reminders documented as backend/device scheduled behavior, optionally using synthetic bridge input for phrasing.
4. Add logs around request id, queueing, long-poll delivery, and result completion.

## Recommended next action

Fix the Docker wrapper/run semantics first, then add the bridge round-trip test. Do not spend time on new skills until `BackendChannel.submit()` can be proven to complete through the same `/next` and `/result` protocol the Docker sidecar uses.
