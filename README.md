# LA Hacks 2026

OmegaClaw Glasses Runtime is a scaffold for an OpenClaw-style assistant on Meta Ray-Ban glasses. This repo currently centers on a thin iOS client, a FastAPI backend shell, and the integration plan for a future OmegaClaw + Agentverse flow.

## Current status

This repository is not a full end-to-end glasses runtime yet. Today it contains:

- a generated iOS app shell with WebSocket, debug UI, and scaffolded audio/photo plumbing
- a Python backend with `/health` and an echo-style `/session` WebSocket
- product and architecture guidance in `PRD.md`

It does not yet contain a real Gemini Live bridge, a checked-in OmegaClaw adapter, or a checked-in Agentverse skill service. Treat this repo as the shared scaffold for four parallel tracks rather than a finished demo.

## Four-track architecture

### 1. iOS track

The iPhone app is the local shell for Meta glasses sessions. It handles UI, WebSocket transport, mic/photo capture, debug state, and the future glasses hardware path.

### 2. Backend track

The backend owns the session lifecycle and will eventually become the live bridge for streaming audio, transcripts, tool calls, and look requests.

### 3. OmegaClaw track

OmegaClaw is the orchestration layer described in `PRD.md`. It is planned to receive structured task context from the live session, decide whether to answer or delegate, and route specialist work through its skill system.

### 4. Agentverse track

Agentverse is the planned specialist-skill layer. The first target skill is `identify_person`, but that service is still roadmap work and is not implemented in this repo today.

## Repo layout

```text
.
|-- apps/
|   `-- ios/                  # XcodeGen-based iOS client
|-- backend/                  # FastAPI backend scaffold
|-- docs/
|   `-- gemini-api/           # reference material
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
# add GEMINI_API_KEY when you are ready for future live-model work
uv sync
uv run python main.py
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

For a physical iPhone, update `BackendWebSocketURL` in `apps/ios/project.yml` to your Mac's LAN IP and rerun `xcodegen`.

## Track-by-track setup

### iOS track setup

- Read [`apps/ios/README.md`](apps/ios/README.md).
- Generate the Xcode project with `xcodegen`.
- Run on a simulator or physical iPhone.
- Use the current app as a scaffold for session UI, debug views, and future DAT hardware validation.

### Backend track setup

- Read [`backend/README.md`](backend/README.md).
- Create `backend/.env` from `.env.example`.
- Install dependencies with `uv sync`.
- Run `uv run python main.py`.
- Use the current backend for local health checks and WebSocket protocol validation, not as a full live assistant yet.

### OmegaClaw track setup

- Read [`PRD.md`](PRD.md) first.
- Use the PRD's OmegaClaw references to design the channel adapter and remote-skill wiring.
- Expect this work to happen in a separate OmegaClaw clone or integration workspace until the adapter code is brought into this repo.

Current honesty: there is no checked-in `channels/` adapter or OmegaClaw runtime code here yet.

### Agentverse track setup

- Read [`PRD.md`](PRD.md) for the `identify_person` skill contract, response shape, and registration flow.
- Stand up the skill service in its own workspace or service repo first.
- Register and externally verify the agent before wiring it back through OmegaClaw.

Current honesty: the Agentverse skill is specified, but not implemented in this repo yet.

## Roadmap and what's missing

The repo is aligned around four active gaps:

- iOS: finish continuous mic streaming, real DAT still capture, and end-to-end device verification
- backend: replace the echo session with a real Gemini Live bridge that streams transcripts, audio, and tool events
- OmegaClaw: add the actual channel adapter and skill dispatch path
- Agentverse: implement, host, register, and validate the first flagship skill

The near-term milestone is a true speech -> backend -> OmegaClaw -> Agentverse -> spoken response loop. Until that exists, the correct description of this codebase is "scaffold with the right shape," not "complete runtime."

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
