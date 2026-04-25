# Backend

FastAPI backend for the glasses assistant.

## Environment

Copy the example file and choose the live backend:

```bash
cp .env.example .env
```

```env
# Default local development mode. Override to `gemini` to use Gemini Live.
LIVE_BACKEND=echo

# Required when LIVE_BACKEND=gemini.
GEMINI_API_KEY=your_key_here

# Optional Gemini Live settings.
GEMINI_LIVE_MODEL=gemini-live-2.5-flash-preview
GEMINI_API_VERSION=v1alpha
GEMINI_RESPONSE_MODALITIES=TEXT
```

`LIVE_BACKEND=echo` is the safe default and does not require Gemini credentials. Set
`LIVE_BACKEND=gemini` to enable the Gemini Live adapter. The current router still
exposes the Phase 1 `/health` endpoint plus the echo `/session` WebSocket, while
the new adapter layer is ready for coordinator wiring in the next phase.
