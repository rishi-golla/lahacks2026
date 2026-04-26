# Google Shared Glasses Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Google-connected Edith site and backend flow that lets one current site-linked user enable protected Google actions from the shared Meta glasses after spoken confirmation.

**Architecture:** The backend owns Google OAuth, active linked-user state, action history, and pending confirmation state. Edith becomes the connect/history UI. The existing Gemini -> backend -> OmegaClaw path remains the entrypoint for glasses requests, but protected Google actions now pause for confirmation and then execute through backend-managed Google services.

**Tech Stack:** FastAPI, existing backend session/OmegaClaw flow, React + Vite, TypeScript, Google OAuth 2.0 web server flow, Google API Python client libraries

---

### Task 1: Add backend state models and API surface for linked user + history

**Files:**
- Create: `backend/app/google/__init__.py`
- Create: `backend/app/google/models.py`
- Create: `backend/app/google/store.py`
- Create: `backend/app/routers/google.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_google_routes.py`

- [ ] **Step 1: Write the failing tests**

Write tests for:
- `GET /google/status` returns disconnected state by default
- `GET /google/history` returns an empty list by default
- disconnect clears linked user state

- [ ] **Step 2: Run tests to verify they fail**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_google_routes.py -v`
Expected: FAIL because the router and store do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement:
- in-memory store for active linked user and action history
- `GET /google/status`
- `GET /google/history`
- `POST /google/disconnect`
- router registration in `backend/app/main.py`

- [ ] **Step 4: Run tests to verify they pass**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_google_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/google backend/app/routers/google.py backend/app/main.py backend/tests/test_google_routes.py
git commit -m "feat: add google linked-user status and history api"
```

### Task 2: Add Google OAuth service and callback flow

**Files:**
- Create: `backend/app/google/oauth.py`
- Modify: `backend/app/google/models.py`
- Modify: `backend/app/google/store.py`
- Modify: `backend/app/routers/google.py`
- Modify: `backend/pyproject.toml`
- Test: `backend/tests/test_google_oauth.py`

- [ ] **Step 1: Write the failing tests**

Write tests for:
- start endpoint returns a redirect URL or auth start payload
- callback stores linked user identity and granted scopes
- missing config returns a clear setup error

- [ ] **Step 2: Run tests to verify they fail**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_google_oauth.py -v`
Expected: FAIL because OAuth service does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement:
- Google OAuth config model
- auth start flow
- callback handler
- linked user persistence
- required Google client dependencies in `backend/pyproject.toml`

- [ ] **Step 4: Run tests to verify they pass**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_google_oauth.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/google backend/app/routers/google.py backend/pyproject.toml backend/tests/test_google_oauth.py
git commit -m "feat: add google oauth connect flow"
```

### Task 3: Add protected action confirmation and Google action execution services

**Files:**
- Create: `backend/app/google/actions.py`
- Create: `backend/app/google/confirmation.py`
- Modify: `backend/app/google/store.py`
- Modify: `backend/app/session/live_adapter.py`
- Modify: `omegaclaw/runtime_loop.py`
- Test: `backend/tests/test_google_confirmation.py`
- Test: `backend/tests/test_live_adapter.py`

- [ ] **Step 1: Write the failing tests**

Write tests for:
- protected action without linked user is refused
- protected action with linked user creates a pending confirmation prompt
- `yes` executes the pending action
- non-yes cancels the action
- history records the outcome

- [ ] **Step 2: Run tests to verify they fail**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_google_confirmation.py backend\tests\test_live_adapter.py -k "google or confirm" -v`
Expected: FAIL because confirmation state and action execution do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement:
- protected intent list
- pending action store
- confirmation parser for spoken `yes`
- live adapter logic to ask for identity confirmation
- Google action executor stubs for gmail, calendar, and tasks
- history logging for confirmed, denied, and failed actions
- `google_tasks` routing support if missing from OmegaClaw

- [ ] **Step 4: Run tests to verify they pass**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_google_confirmation.py backend\tests\test_live_adapter.py -k "google or confirm" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/google backend/app/session/live_adapter.py omegaclaw/runtime_loop.py backend/tests/test_google_confirmation.py backend/tests/test_live_adapter.py
git commit -m "feat: add google action confirmation flow"
```

### Task 4: Turn Edith into the connect + history dashboard

**Files:**
- Create: `apps/edith/src/lib/api.ts`
- Modify: `apps/edith/src/App.tsx`
- Modify: `apps/edith/src/index.css`
- Test: `apps/edith` build verification

- [ ] **Step 1: Write the failing frontend expectation**

Define the UI behaviors to implement:
- disconnected state with connect CTA
- connected state with linked user identity
- history list
- disconnect action

- [ ] **Step 2: Run build to establish baseline**

Run: `npm run build`
Workdir: `apps/edith`
Expected: PASS before changes so regressions are obvious.

- [ ] **Step 3: Write minimal implementation**

Implement:
- frontend API client for backend routes
- connect button that navigates to backend OAuth start
- status fetch and history fetch
- connected/disconnected cards
- history timeline UI

- [ ] **Step 4: Run build to verify it passes**

Run: `npm run build`
Workdir: `apps/edith`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/edith/src/App.tsx apps/edith/src/index.css apps/edith/src/lib/api.ts
git commit -m "feat: add google connect dashboard to edith"
```

### Task 5: Verify end-to-end behavior and document setup

**Files:**
- Modify: `README.md`
- Modify: `backend/README.md`
- Modify: `apps/edith/README.md` (create if missing)
- Test: targeted backend pytest suite
- Test: `apps/edith` build

- [ ] **Step 1: Write the failing documentation checklist**

Document required env vars and local run steps for:
- Google OAuth client config
- backend start
- Edith start
- expected action confirmation flow

- [ ] **Step 2: Run verification commands before doc updates**

Run:
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_google_routes.py backend\tests\test_google_oauth.py backend\tests\test_google_confirmation.py backend\tests\test_live_adapter.py backend\tests\test_omegaclaw_channel.py backend\tests\test_omegaclaw_runtime_loop.py backend\tests\test_omegaclaw_remote_bridge.py backend\tests\test_omegaclaw_extension_points.py`
- `npm run build` in `apps/edith`

Expected: PASS after implementation.

- [ ] **Step 3: Write minimal documentation**

Update docs with:
- required Google Cloud setup
- new backend env vars
- how the shared-glasses linked-user model works
- what spoken confirmation looks like

- [ ] **Step 4: Re-run final verification**

Run the same commands again and confirm everything is green.

- [ ] **Step 5: Commit**

```bash
git add README.md backend/README.md apps/edith/README.md
git commit -m "docs: add google shared glasses setup guide"
```
