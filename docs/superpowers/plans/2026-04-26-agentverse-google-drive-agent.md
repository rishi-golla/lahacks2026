# Agentverse Google Drive Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Agentverse/uAgent Google Drive worker that supports chat and typed request/response for search, download, upload, move, and delete operations using one fixed Google Drive account.

**Architecture:** Mirror the mail agent pattern. Keep the implementation in one Python file with helper functions for ASI:One extraction, Drive token refresh, and each Drive action. Support both natural-language chat and typed inter-agent requests.

**Tech Stack:** Python, `uagents`, `uagents_core`, `openai` (ASI:One endpoint), Google Drive REST API, base64 file payloads

---

### Task 1: Create the Drive agent scaffold and structured models

**Files:**
- Create: `agents/google_drive_agent.py`
- Create: `backend/tests/test_google_drive_agent_protocol.py`

- [ ] **Step 1: Write the failing protocol test**
Add tests for:
- chat request acknowledgment
- structured request success path
- structured request error path

- [ ] **Step 2: Run the test to verify it fails**
Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_google_drive_agent_protocol.py -q`
Expected: FAIL because the file does not exist yet.

- [ ] **Step 3: Create the minimal agent scaffold**
Implement:
- `GoogleDriveRequest`
- `GoogleDriveResponse`
- chat protocol imports/fallbacks
- `Agent`
- `Protocol`

- [ ] **Step 4: Re-run the protocol test**
Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_google_drive_agent_protocol.py -q`
Expected: still FAIL, but now in helper logic instead of import/setup.

### Task 2: Add request extraction for chat mode

**Files:**
- Modify: `agents/google_drive_agent.py`
- Create: `backend/tests/test_google_drive_agent_extraction.py`

- [ ] **Step 1: Write the failing extraction test**
Mock ASI:One and verify `extract_drive_request(text)` returns:
- `action`
- relevant IDs/fields for that action

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement `extract_drive_request(...)`**
Use ASI:One to return JSON with the normalized action and fields.

- [ ] **Step 4: Re-run the extraction test**
Expected: PASS

### Task 3: Add Google Drive API helpers

**Files:**
- Modify: `agents/google_drive_agent.py`
- Create: `backend/tests/test_google_drive_agent_actions.py`

- [ ] **Step 1: Write failing tests for Drive helpers**
Cover:
- token refresh
- `search_drive_files(...)`
- `download_drive_file(...)`
- `upload_drive_file(...)`
- `move_drive_file(...)`
- `delete_drive_file(...)`

- [ ] **Step 2: Run tests to verify failure**

- [ ] **Step 3: Implement the minimal helpers**
Use env vars:
- `GDRIVE_CLIENT_ID`
- `GDRIVE_CLIENT_SECRET`
- `GDRIVE_REFRESH_TOKEN`
- optional `GDRIVE_TOKEN_URI`
- optional `GDRIVE_ROOT_FOLDER_ID`

- [ ] **Step 4: Re-run the helper tests**
Expected: PASS

### Task 4: Wire chat and typed request handlers

**Files:**
- Modify: `agents/google_drive_agent.py`
- Modify: `backend/tests/test_google_drive_agent_protocol.py`

- [ ] **Step 1: Implement chat request handling**
Map the extracted action to the correct Drive helper and return a concise chat summary.

- [ ] **Step 2: Implement typed request handling**
Support the actions:
- `search`
- `download`
- `upload`
- `move`
- `delete`

- [ ] **Step 3: Re-run protocol tests**
Expected: PASS

### Task 5: Verify the whole Drive agent

**Files:**
- Modify: `agents/google_drive_agent.py`

- [ ] **Step 1: Run all Drive agent tests**
Run:
`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_google_drive_agent_protocol.py backend\tests\test_google_drive_agent_extraction.py backend\tests\test_google_drive_agent_actions.py -q`

- [ ] **Step 2: Ensure top-of-file usage docs are present**
Document required env vars and run command.

- [ ] **Step 3: Commit**

```bash
git add agents/google_drive_agent.py backend/tests/test_google_drive_agent_*.py docs/superpowers/specs/2026-04-26-agentverse-google-drive-agent-design.md docs/superpowers/plans/2026-04-26-agentverse-google-drive-agent.md
git commit -m "feat: add standalone agentverse google drive agent"
```
