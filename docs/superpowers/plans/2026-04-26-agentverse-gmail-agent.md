# Agentverse Gmail Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Agentverse/uAgent Python file that drafts and sends HTML Gmail messages automatically from one fixed Gmail account.

**Architecture:** Keep the implementation as a single runnable agent file based on the provided Agentverse chat template, but split logic into helper functions for request extraction, HTML email construction, and Gmail API sending. Use ASI:One for structured email drafting and Gmail API for execution.

**Tech Stack:** Python, `uagents`, `uagents_core`, `openai` (ASI:One endpoint), Gmail REST API, MIME email formatting

---

### Task 1: Create the agent file scaffold

**Files:**
- Create: `agents/mail_sending_agent.py`
- Test: `backend/tests/test_mail_sending_agent_formatting.py`

- [ ] **Step 1: Write the failing formatting test**

Add a test that imports the helper responsible for building the HTML email and asserts that the output includes:
- HTML tags
- `Rishi Golla`
- `Sent by Edith, my AI Agent`
- the Cloudinary image URL
- `www.asi1.ai`

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_mail_sending_agent_formatting.py -q`
Expected: FAIL because the file or helper does not exist yet.

- [ ] **Step 3: Create the minimal agent file scaffold**

Create a file based on the user-provided Agentverse template with:
- imports
- `OpenAI` client using `https://api.asi1.ai/v1`
- `Agent(...)`
- `Protocol(spec=chat_protocol_spec)`
- protocol handlers for `ChatMessage` and `ChatAcknowledgement`

- [ ] **Step 4: Add a minimal `build_html_email(...)` helper**

Implement the helper with the required signature block and simple HTML structure so the formatting test can pass.

- [ ] **Step 5: Re-run the test**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_mail_sending_agent_formatting.py -q`
Expected: PASS

### Task 2: Add structured email extraction through ASI:One

**Files:**
- Modify: `agents/mail_sending_agent.py`
- Create: `backend/tests/test_mail_sending_agent_extraction.py`

- [ ] **Step 1: Write the failing extraction test**

Add a test that mocks the ASI:One client and verifies `extract_email_request(text)` returns a dict with fields like:
- `recipient`
- `subject_hint`
- `body_intent`

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_mail_sending_agent_extraction.py -q`
Expected: FAIL because the helper is incomplete.

- [ ] **Step 3: Implement `extract_email_request(...)`**

Call ASI:One with a system prompt that extracts structured email intent and returns JSON-like content.

- [ ] **Step 4: Re-run the extraction test**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_mail_sending_agent_extraction.py -q`
Expected: PASS

### Task 3: Add Gmail API send support

**Files:**
- Modify: `agents/mail_sending_agent.py`
- Create: `backend/tests/test_mail_sending_agent_gmail_send.py`

- [ ] **Step 1: Write the failing Gmail send test**

Add a test that mocks:
- token refresh request
- Gmail send request

Assert that the helper:
- uses HTML MIME content
- base64url-encodes the message
- returns a success identifier on success

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_mail_sending_agent_gmail_send.py -q`
Expected: FAIL because Gmail sending is not implemented yet.

- [ ] **Step 3: Implement `send_gmail_message(...)`**

Read env vars:
- `GMAIL_SENDER_EMAIL`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`
- optional `GMAIL_TOKEN_URI`

Refresh the access token, build the MIME message, and send it via Gmail API.

- [ ] **Step 4: Re-run the Gmail send test**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_mail_sending_agent_gmail_send.py -q`
Expected: PASS

### Task 4: Wire the chat handler end to end

**Files:**
- Modify: `agents/mail_sending_agent.py`
- Create: `backend/tests/test_mail_sending_agent_protocol.py`

- [ ] **Step 1: Write the failing protocol test**

Add a test that simulates a `ChatMessage`, mocks extraction + Gmail send, and asserts that the response:
- acknowledges receipt
- returns a `ChatMessage`
- includes a short success or clarification response
- ends the session

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_mail_sending_agent_protocol.py -q`
Expected: FAIL because the end-to-end behavior is incomplete.

- [ ] **Step 3: Implement the full handler flow**

Inside `@protocol.on_message(ChatMessage)`:
- ack the message
- extract text
- call extraction helper
- validate required fields
- build subject + HTML body
- send email
- respond with success or clarification/failure

- [ ] **Step 4: Run the protocol test**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_mail_sending_agent_protocol.py -q`
Expected: PASS

### Task 5: Run verification and document usage

**Files:**
- Modify: `agents/mail_sending_agent.py`
- Optionally create: `agents/README-mail-sending-agent.md`

- [ ] **Step 1: Run all new Gmail agent tests**

Run:
`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_mail_sending_agent_formatting.py backend\tests\test_mail_sending_agent_extraction.py backend\tests\test_mail_sending_agent_gmail_send.py backend\tests\test_mail_sending_agent_protocol.py -q`

Expected: all PASS

- [ ] **Step 2: Add a short top-of-file usage block**

Document required env vars and how to run:
- `python agents/mail_sending_agent.py`

- [ ] **Step 3: Commit**

```bash
git add agents/mail_sending_agent.py backend/tests/test_mail_sending_agent_*.py docs/superpowers/specs/2026-04-26-agentverse-gmail-agent-design.md docs/superpowers/plans/2026-04-26-agentverse-gmail-agent.md
git commit -m "feat: add standalone agentverse gmail sending agent"
```
