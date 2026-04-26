# LA Hacks 2026

OmegaClaw Glasses Runtime is an OpenClaw-style assistant prototype for Meta Ray-Ban glasses. The repo currently centers on a thin iOS client, a FastAPI backend with a real Gemini Live bridge, and an in-progress OmegaClaw + Agentverse integration path.

## Current status

This repository is not a polished end-to-end glasses runtime yet. Today it contains:

- an iOS debug app with WebSocket transport, audio loopback/playback, mock/real glasses modes, DAT registration UI, and manual photo capture
- a Python backend with `/health`, `/session`, echo mode, and real Gemini Live mode
- local OmegaClaw and ContextLens/Agentverse integration modules
- product and architecture guidance in `PRD.md`

It does not yet contain Gemini tool declarations, automatic vision capture on typed prompts, or a fully verified real-glasses photo path. Treat this repo as an active prototype rather than a finished demo.

## Four-track architecture

### 1. iOS track

The iPhone app is the local shell for Meta glasses sessions. It handles UI, WebSocket transport, mic/photo capture, debug state, and the future glasses hardware path.

### 2. Backend track

The backend owns the session lifecycle and is now the live bridge for Gemini text/audio/photo traffic. Tool calls and automatic look requests are still pending.

### 3. OmegaClaw track

OmegaClaw is the orchestration layer described in `PRD.md`. It is planned to receive structured task context from the live session, decide whether to answer or delegate, and route specialist work through its skill system.

### 4. Agentverse track

Agentverse is the specialist-skill layer. The local `contextlens-agent/` service exists as the current checked-in skill/service surface.

## Repo layout

```text
.
|-- apps/
|   `-- ios/                  # XcodeGen-based iOS client
|-- backend/                  # FastAPI backend and Gemini Live bridge
|-- contextlens-agent/         # ContextLens FastAPI + uAgents skill service
|-- docs/
|   `-- gemini-api/           # reference material
|-- PeTTa/repos/OmegaClaw-Core # vendored OmegaClaw-Core (Docker image build + scripts/omegaclaw)
|-- PRD.md                    # product + architecture source of truth
`-- README.md                 # this overview
```

## Quick start

If you only want the local scaffold running:

1. Start the backend.
2. Generate and open the iOS project.
3. Point the iOS app at the backend WebSocket.

### Backend

```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The current local endpoint is `ws://127.0.0.1:8000/session`.

### iOS

```bash
brew install xcodegen
cd apps/ios
xcodegen
open MetaGlassesAgent.xcodeproj
```

In Xcode:

1. Let Swift Package Manager resolve dependencies.
2. Set your Personal Team in Signing & Capabilities.
3. Run the `MetaGlassesAgent` scheme.

For a physical iPhone, enter a `wss://.../session` ngrok URL in the app's backend URL field.

## Starting everything locally

Typical order: **backend** (with the bridge enabled if you use Docker OmegaClaw below), **OmegaClaw container** (optional), then **iOS** pointed at `ws://127.0.0.1:8000/session` (or your tunnel URL).

### Backend

Same as [Quick start → Backend](#backend). For the Docker OmegaClaw HTTP bridge, set `OMEGACLAW_BRIDGE_ENABLED=1` in `backend/.env` (see commented lines in `backend/.env.example`) and keep the API on port **8000** so the container’s default `http://host.docker.internal:8000` base URL works on macOS.

### OmegaClaw (Docker)

From the vendored core tree (paths match [`docs/OMEGACLAW_DOCKER_WORKFLOW.md`](docs/OMEGACLAW_DOCKER_WORKFLOW.md)):

```bash
cd PeTTa/repos/OmegaClaw-Core
docker build -t my-omegaclaw:dev .
./scripts/omegaclaw my-omegaclaw:dev
```

The script prompts for a channel, LLM provider, and API key. Choose **option 3** (LA Hacks HTTP bridge) so the container long-polls this repo’s backend at `/internal/omegaclaw/next`. Start the backend with the bridge enabled before answering those prompts.

**Clean up** (removes the container and its named memory volume):

```bash
docker stop omegaclaw
docker rm -f omegaclaw
docker volume rm omegaclaw-memory
```

The wrapper already runs `docker rm -f omegaclaw` before starting a new container; use the full cleanup when you want to drop persisted MeTTa memory.

### iOS

Same as [Quick start → iOS](#ios). See [`apps/ios/README.md`](apps/ios/README.md) for signing and scheme details.

## Track-by-track setup

### iOS track setup

- Read [`apps/ios/README.md`](apps/ios/README.md).
- Generate the Xcode project with `xcodegen`.
- Run on a simulator or physical iPhone.
- Use the current app for session UI, debug views, audio playback, DAT validation, and mock/real photo capture testing.

### Backend track setup

- Read [`backend/README.md`](backend/README.md).
- Create `backend/.env` from `.env.example`.
- Install dependencies with `uv sync`.
- Run `uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
- Use `LIVE_BACKEND=gemini` for real Gemini Live testing.

### OmegaClaw track setup

- Read [`PRD.md`](PRD.md) first.
- For a runnable Docker sidecar against this backend, follow [Starting everything locally → OmegaClaw (Docker)](#omegaclaw-docker) and [`docs/OMEGACLAW_DOCKER_WORKFLOW.md`](docs/OMEGACLAW_DOCKER_WORKFLOW.md) / [`docs/omegaclaw_bridge_runbook.md`](docs/omegaclaw_bridge_runbook.md).

Current honesty: OmegaClaw adapter/runtime code is checked in, but Gemini is not yet wired to call it as an `agent` tool.

### Agentverse track setup

- Read [`PRD.md`](PRD.md) for the `identify_person` skill contract, response shape, and registration flow.
- Stand up the skill service in its own workspace or service repo first.
- Register and externally verify the agent before wiring it back through OmegaClaw.

Current honesty: `contextlens-agent/` is checked in, but the full Gemini -> OmegaClaw -> Agentverse loop is not wired into the live session yet.

## Roadmap and what's missing

The repo is aligned around four active gaps:

- iOS: add deterministic photo-before-vision-question behavior and verify real DAT still capture
- backend: declare/handle Gemini tools only after the direct visual path is stable
- OmegaClaw: connect the checked-in adapter path to Gemini's future `agent` tool
- Agentverse: host/register/validate the checked-in ContextLens service

The near-term milestone is reliable speech + fresh visual context through the iOS app and Gemini. After that, the target is Gemini -> OmegaClaw -> Agentverse -> spoken response.

## References

- [`PRD.md`](PRD.md)
- [`apps/ios/README.md`](apps/ios/README.md)
- [`backend/README.md`](backend/README.md)
- VisionClaw: https://github.com/Intent-Lab/VisionClaw
- OmegaClaw docs index: https://github.com/asi-alliance/OmegaClaw-Core/blob/main/docs/README.md
- OmegaClaw channel tutorial: https://github.com/asi-alliance/OmegaClaw-Core/blob/main/docs/tutorial-04-adding-a-channel.md
- OmegaClaw remote Agentverse tutorial: https://github.com/asi-alliance/OmegaClaw-Core/blob/main/docs/tutorial-06-remote-agentverse-skills.md
- Agentverse: https://agentverse.ai
- Gemini Live API: https://ai.google.dev/gemini-api/docs/live
- Meta Ray-Ban / DAT SDK docs: https://developers.facebook.com/docs/ray-ban-meta-smart-glasses
