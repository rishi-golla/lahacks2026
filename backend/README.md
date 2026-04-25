# Backend

FastAPI backend for the glasses assistant.

## Environment

Copy the example file and add your Gemini API key:

```bash
cp .env.example .env
```

```env
GEMINI_API_KEY=your_key_here
```

The current Phase 1 backend only exposes `/health` and the echo `/session` WebSocket. Phase 4 will use the Gemini settings in `.env`.
