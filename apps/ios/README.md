# MetaGlassesAgent iOS

Thin iOS client for the Meta glasses assistant. The app captures mic/photo input, sends JSON messages to the backend WebSocket, and displays debug state for transcripts, tool events, and photos.

## Setup

```bash
brew install xcodegen
cd apps/ios
xcodegen
open MetaGlassesAgent.xcodeproj
```

In Xcode:

1. Wait for Swift Package Manager to resolve `meta-wearables-dat-ios`.
2. Select your Personal Team under Signing & Capabilities.
3. Run the `MetaGlassesAgent` scheme.

## Backend URL

The default WebSocket URL is stored in `project.yml` as:

```text
ws://localhost:8000/session
```

For a physical iPhone, prefer entering an ngrok `wss://.../session` URL in the app's Backend WebSocket URL field. The checked-in default remains useful for simulator/local development:

```text
wss://<your-ngrok-host>/session
```

## Current State

The app is past the scaffold stage. Current behavior:

- WebSocket client and protocol messages are implemented.
- Debug UI includes backend URL entry, Mock/Real glasses toggle, DAT status, loopback, manual capture, typed send, and logs.
- Audio loopback and Gemini audio playback work.
- Mock glasses mode uses bundled media.
- Real glasses mode has DAT session/photo capture code, but the real camera path still needs on-device verification.
- Pressing `Send` currently sends text only.
- Pressing `Capture Photo` sends a photo.
- Automatic photo capture before vision-style prompts is the next iOS change.
