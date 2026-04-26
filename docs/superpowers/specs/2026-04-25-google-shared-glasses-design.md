# Google Shared Glasses Workflow Design

**Date:** 2026-04-25

## Goal

Allow a single person at a time to visit the Edith site, connect their Google account, and enable Google-backed action tasks from the shared Meta glasses. The glasses remain usable for general conversation by anyone, but protected Google actions only run when a site-linked user exists and confirms their identity by voice.

## Product Flow

1. A user opens the Edith site and connects Google.
2. The backend stores that user as the current action-enabled user.
3. Anyone can still use the glasses for non-Google requests.
4. When a spoken command requires Gmail, Calendar, or Tasks, the backend checks for an active linked user.
5. If none exists, the glasses refuse the action and instruct the user to connect on the site.
6. If a linked user exists, the glasses ask: "Before I continue, just to confirm, are you <name>?"
7. If the user says `yes`, the backend executes the pending action and logs it to history.
8. If the user does not confirm, the backend cancels the pending action and logs the denial.
9. The Edith site shows the linked user state and action history.

## Architecture

### Frontend

`apps/edith` becomes the live Google connect and history dashboard. It is responsible for:

- showing the current linked user
- starting the Google OAuth connect flow
- disconnecting the current linked user
- polling or fetching action history
- presenting the system state in a demo-friendly way

### Backend

`backend` becomes the system of record for:

- active linked user identity
- OAuth credentials and refresh tokens
- pending protected action confirmation state
- action execution results
- history/audit events

The existing session and OmegaClaw integration stays in the backend. Google auth and action state should not be spread across agents.

### OmegaClaw

`omegaclaw` continues to classify and route intents such as `gmail`, `google_calendar`, and `google_tasks`. Protected actions are subject to backend confirmation and user-link checks before execution.

### Google Integration

The recommended implementation is backend-owned Google access using the server-side OAuth authorization code flow for web applications. This follows Google’s web server OAuth guidance and keeps refresh tokens server-side instead of inside the frontend.

## Key State Models

### Active Linked User

Represents the one current Google-connected user whose account can be used for protected actions from the shared glasses.

Fields:

- `display_name`
- `email`
- `google_subject`
- `granted_scopes`
- `connected_at`
- `status`

### Pending Protected Action

Represents one in-progress Google action waiting on voice confirmation.

Fields:

- `id`
- `intent`
- `prompt_text`
- `user_display_name`
- `args`
- `created_at`
- `expires_at`
- `status`

### Action History Event

Represents every attempted protected action for site visibility and debugging.

Fields:

- `id`
- `timestamp`
- `intent`
- `actor_email`
- `status`
- `summary`
- `details`

## Protected Action Rules

Protected intents include:

- Gmail draft/send
- Calendar create/update/list actions
- Google Tasks and reminder-style actions

Behavior:

- No linked user: return a refusal and instruct the user to connect on the site.
- Linked user exists: create a pending action and ask for spoken confirmation.
- Spoken `yes`: execute immediately.
- Any other response or timeout: cancel the action.

General conversational tasks and non-Google tasks skip this flow.

## API Surface

### Edith-facing backend APIs

- `GET /google/status`
- `POST /google/connect/start`
- `GET /google/connect/callback`
- `POST /google/disconnect`
- `GET /google/history`

### Internal backend services

- Google OAuth service
- Active user store
- Action history store
- Pending confirmation store
- Google action executor service

## Session Integration

The live adapter already routes Gemini `agent` tool calls into the backend OmegaClaw path. The new behavior should extend this path:

1. Gemini identifies a Google-backed intent.
2. OmegaClaw routes to a protected skill.
3. Backend checks linked user state.
4. Backend asks for spoken confirmation instead of executing immediately.
5. On `yes`, backend executes the pending action through Google APIs.
6. Backend returns the spoken result and logs the outcome.

## Google API Scope Strategy

For v1, request only the scopes needed for supported tasks. The exact list should stay minimal even though the product story is “your Google workflow.”

Expected initial scopes:

- Gmail send/compose scopes
- Calendar event scopes
- Google Tasks scopes
- OpenID profile/email scopes for identity display

## Error Handling

- Missing Google client configuration: site shows setup error.
- OAuth failure: backend clears partial state and returns a connect error.
- Missing linked user during action request: backend refuses action.
- Confirmation timeout: backend cancels pending action.
- Google API failure: backend logs failure and speaks a concise failure message.
- Revoked token: backend clears linked user state and prompts reconnect on the site.

## Testing Strategy

### Backend

- OAuth start endpoint builds the right redirect flow.
- OAuth callback stores linked user state.
- Protected actions without linked user are refused.
- Protected actions with linked user create pending confirmation.
- Saying `yes` executes the pending action.
- Saying anything else cancels it.
- History records success, denial, timeout, and failure states.

### Frontend

- Edith shows disconnected, connected, and error states.
- Connect button routes to backend auth start.
- Disconnect clears the active user view.
- History renders backend events.

### Integration

- Spoken protected command -> confirmation prompt -> `yes` -> action execution
- Spoken protected command -> confirmation prompt -> non-yes -> cancellation

## Repo Mapping

- `apps/edith/src/App.tsx`: replace static landing-only behavior with connect and history UI
- `backend/app/`: add Google auth, linked user state, history, and protected action services
- `backend/app/session/live_adapter.py`: integrate pending confirmation and protected action execution
- `omegaclaw/`: keep current routing, add `google_tasks` if missing

## External References

- Google OAuth 2.0 for Web Server Applications: https://developers.google.com/identity/protocols/oauth2/web-server
- Gmail API Python quickstart: https://developers.google.com/workspace/gmail/api/quickstart/python
- Google Calendar API overview: https://developers.google.com/workspace/calendar/api/guides/overview
- Google Tasks Python quickstart: https://developers.google.com/workspace/tasks/quickstart/python
