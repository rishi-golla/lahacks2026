# LA Hacks 2026

OmegaClaw Glasses Runtime is an OpenClaw-style assistant prototype for Meta Ray-Ban glasses. The repo currently centers on a thin iOS client, a FastAPI backend with a real Gemini Live bridge, and an in-progress OmegaClaw + Agentverse integration path.

## Current status

This repository is not a polished end-to-end glasses runtime yet. Today it contains:

- an iOS debug app with WebSocket transport, audio loopback/playback, mock/real glasses modes, DAT registration UI, and manual photo capture
- a Python backend with `/health`, `/session`, echo mode, and real Gemini Live mode
- a Google-connected Edith site for linking one current action-enabled user and viewing shared-glasses history
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
|   |-- edith/                # Google connect + activity history site
|   `-- ios/                  # XcodeGen-based iOS client
|-- backend/                  # FastAPI backend and Gemini Live bridge
|-- contextlens-agent/         # ContextLens FastAPI + uAgents skill service
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
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The current local endpoint is `ws://127.0.0.1:8000/session`.

To enable Google connect from the Edith site, also configure:

```env
GOOGLE_OAUTH_CLIENT_ID=your_google_web_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_google_web_client_secret
GOOGLE_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/google/connect/callback
```

### Edith

```bash
cd apps/edith
npm install
npm run dev
```

Edith expects the backend on `http://127.0.0.1:8000` by default.

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
- Use the PRD's OmegaClaw references to design the channel adapter and remote-skill wiring.
- Expect this work to happen in a separate OmegaClaw clone or integration workspace until the adapter code is brought into this repo.

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

For the shared-glasses Google workflow, the current implementation is:

- a user connects Google on Edith
- that user becomes the current action-enabled user for the shared glasses
- protected Gmail/Calendar/Tasks actions require spoken confirmation
- the site shows the resulting activity history

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
