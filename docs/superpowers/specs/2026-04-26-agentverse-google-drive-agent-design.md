# Agentverse Google Drive Agent Design

**Goal**

Create a standalone Agentverse/uAgent Google Drive worker that can search, download, upload, move, and delete files using one fixed Google Drive account, and expose both chat-style interaction and a typed request/response interface for other agents such as the mail agent.

## Recommended approach

Use one all-purpose Drive agent. It is the fastest path, keeps the inter-agent surface simple, and matches the standalone Gmail and Calendar agents already being built.

## Behavior

The agent should support:

- search for files
- download files
- upload files
- move files between folders
- delete files

It should work in two modes:

1. **Chat mode**
   - Accept a natural-language file request
   - Convert it into a structured Drive action
   - Return a concise summary

2. **Structured request/response mode**
   - Accept a typed action request from another agent
   - Return a typed response with stable fields and IDs

This makes it usable by both humans and other agents.

## Structured interface

The request model should include:

- `action`
- optional `query`
- optional `file_id`
- optional `folder_id`
- optional `target_folder_id`
- optional `filename`
- optional `mime_type`
- optional `content_b64`

Supported actions:

- `search`
- `download`
- `upload`
- `move`
- `delete`

The response model should include:

- `status`
- `action`
- `message`
- optional `file_id`
- optional `file_name`
- optional `mime_type`
- optional `download_b64`
- optional `web_view_link`

## Auth

Use one fixed Google Drive account via environment variables:

- `ASI1_API_KEY`
- `GDRIVE_CLIENT_ID`
- `GDRIVE_CLIENT_SECRET`
- `GDRIVE_REFRESH_TOKEN`
- optional `GDRIVE_TOKEN_URI`
- optional `GDRIVE_ROOT_FOLDER_ID`

The agent should use refresh-token-based Google OAuth so it can operate without interactive login during runtime.

## Drive operations

### Search

Use the Drive files API to search by name/content-relevant query and return the most useful metadata.

### Download

Return metadata and base64 content for downloadable files when practical.

### Upload

Accept a file name, MIME type, and `content_b64`, then create the file in Drive.

### Move

Update file parents to move the file into a target folder.

### Delete

Only delete or trash files when explicitly requested.

## Agent collaboration

The mail agent and other agents should be able to use this Drive agent as a file worker. Example flow:

1. Mail agent asks Drive agent to search for a deck
2. Drive agent returns the selected file ID and metadata
3. Mail agent asks Drive agent to download it
4. Mail agent uses the returned metadata/content to send or reference the file

## Failure behavior

The agent should fail clearly and never pretend a file action succeeded when it did not.

Examples:

- `No file matched that query.`
- `I couldn't upload that file right now.`
- `I couldn't move that file because the target folder was invalid.`

## Architecture

Keep the implementation as one standalone Python file based on the same pattern as the mail and scheduling agents:

- `Agent`
- `Protocol`
- chat handler
- typed request/reply handler
- helper functions for:
  - request extraction
  - token refresh
  - each Drive action

This keeps the agent easy to register and easy to maintain.
