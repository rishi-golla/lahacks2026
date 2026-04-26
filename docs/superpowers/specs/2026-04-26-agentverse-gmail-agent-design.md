# Agentverse Gmail Agent Design

**Goal**

Create a standalone Agentverse/uAgent chat agent that can interpret a user request to draft and send an email, generate the email content automatically, and send it immediately through one fixed Gmail account.

**Why this exists**

The current backend and Meta glasses flow can act as a transport and orchestration layer, but the user wants a directly callable Agentverse agent that can receive a prompt like “draft and send an email to Sarah thanking her for meeting” and complete the send automatically.

## Behavior

When the agent receives a chat message:

1. It acknowledges receipt using the Agentverse chat protocol.
2. It extracts the plain-text user request from the chat content.
3. It asks ASI:One to convert that request into a structured email payload.
4. It generates:
   - an interesting, quirky subject line
   - an HTML email body
   - the required signature block
5. It sends the email through the Gmail API using one fixed Gmail sender account.
6. It returns a short success or failure response through the chat protocol.

If the request is missing a recipient, missing enough message content, or is too ambiguous to safely send, the agent should ask a follow-up question instead of guessing.

## Email rules

The agent should enforce these rules on every sent email:

- subject line should be attention-grabbing and a little quirky
- email body must be HTML
- Gmail send path should mark the body as HTML content
- signature should be from `Rishi Golla`
- include `Sent by Edith, my AI Agent`
- include the 36x36 image at `https://res.cloudinary.com/fetch-ai/image/upload/v1775063969/fetch-llm/onboarding/4_mkezrr.png`
- include `www.asi1.ai` as the final line

## Credentials

This agent should use a single fixed Gmail sender account, not a user-linked Google account.

The agent should read all secrets from environment variables:

- `ASI1_API_KEY`
- `GMAIL_SENDER_EMAIL`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`

Optional:

- `GMAIL_TOKEN_URI` defaulting to `https://oauth2.googleapis.com/token`

The Gmail account should already have API access and a valid refresh token so the agent can send without interactive OAuth during runtime.

## Architecture

The file should stay close to the provided Agentverse template:

- create one `Agent`
- attach one `Protocol(spec=chat_protocol_spec)`
- handle `ChatMessage`
- ignore `ChatAcknowledgement`

Internally, the implementation should be split into helper functions:

- `extract_email_request(text: str) -> dict`
- `build_html_email(payload: dict) -> tuple[str, str]`
- `send_gmail_message(...) -> str`

This keeps the file readable without overengineering it into a full package.

## Gmail send flow

The send flow should use the Gmail API directly, not SMTP and not the existing backend.

Recommended flow:

1. Refresh an access token using the stored refresh token.
2. Build a MIME email with `Content-Type: text/html`.
3. Base64url-encode the raw message.
4. POST to Gmail’s send endpoint:
   - `https://gmail.googleapis.com/gmail/v1/users/me/messages/send`

If Gmail returns success, the agent reports that the email was sent.
If Gmail returns an error, the agent reports the failure clearly.

## Failure behavior

The agent must never claim an email was sent unless Gmail confirms it.

Expected failure modes:

- missing recipient
- missing message content
- model extraction failure
- access token refresh failure
- Gmail API send failure

The user-facing response should stay short and clean:

- success: `Done — I sent the email to ...`
- failure: `I couldn't send that email because ...`
- clarification needed: `Who should I send that to?`

## Integration direction

This agent is intentionally standalone so it can be registered directly in Agentverse. Later, Edith/backend can wrap around it, but that is not required for the initial Agentverse demo.
