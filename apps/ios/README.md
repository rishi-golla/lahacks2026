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

For a physical iPhone, change `BackendWebSocketURL` in `project.yml` to your Mac's LAN IP, then rerun `xcodegen`:

```text
ws://<your-mac-ip>:8000/session
```

## Current State

This is the Phase 2 scaffold. The WebSocket client, message types, UI shell, and platform shapes are present. Audio capture/playback and DAT camera integration include compile-friendly TODOs for Lucas to verify on device/hardware.
