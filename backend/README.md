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
GEMINI_LIVE_MODEL=gemini-2.5-flash-native-audio-preview-12-2025
GEMINI_API_VERSION=v1alpha
GEMINI_RESPONSE_MODALITIES=AUDIO
```

`LIVE_BACKEND=echo` is the safe default and does not require Gemini credentials. Set
`LIVE_BACKEND=gemini` to enable the real Gemini Live adapter. The `/session`
router uses `SessionCoordinator`; it is no longer an echo-only endpoint.

### Google shared-glasses configuration

To enable Google connect and protected action workflows from the Edith site, set:

```env
GOOGLE_OAUTH_CLIENT_ID=your_google_web_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_google_web_client_secret
GOOGLE_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/google/connect/callback
```

The Google Cloud project should enable:

- Gmail API
- Google Calendar API
- Google Tasks API

The OAuth client should be a **Web application** with the backend callback URI
registered as an authorized redirect URI.

Native-audio Gemini Live models accept text, image, and audio inputs, but the
Live response modality should be `AUDIO`; text UI can use the output
transcription events.

## Run

```bash
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Current behavior

- Text uses Gemini Live `send_realtime_input(text=...)`.
- Photos are forwarded as realtime JPEG image/video input.
- Audio output is streamed back as `audio_chunk` messages.
- The Gemini SDK `receive()` iterator is turn-scoped; the backend keeps
  listening across turns.
- No Gemini tools are declared yet, so `look_request` is not triggered by the
  model.
- Google status/history APIs are available at:
  - `GET /google/status`
  - `GET /google/history`
  - `GET /google/connect/start`
  - `GET /google/connect/callback`
  - `POST /google/disconnect`
- Protected Google actions currently use backend-managed confirmation and
  history logging for the shared-glasses flow.

## Smoke tests

Real Gemini calls are scripts, not pytest:

```bash
uv run python ../scripts/gemini_followup_smoke.py
```

Regular unit/integration tests do not call Gemini:

```bash
uv run pytest
```
