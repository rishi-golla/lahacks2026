# ASI:One Browserbase Purchase Agent

This package contains a standalone ASI:One-compatible Agentverse agent for product purchasing assistance. It accepts product metadata, calls a Browserbase-backed worker, searches Amazon, adds the best match to cart, and stops at checkout review.

It does not place orders.

## Files

- `agent.py` - ASI:One Agent Chat Protocol agent for Agentverse upload.
- `browserbase_worker.py` - FastAPI worker that runs Browserbase automation.
- `browserbase_purchase.py` - Stagehand + Browserbase Amazon flow.
- `models.py` - typed request/result models.
- `purchase_client.py` - small HTTP client used by the agent.

## Environment

Agent:

```env
AGENT_SEED=replace-with-agent-seed
AGENT_PORT=8001
AGENT_ENDPOINT=https://your-public-agent-endpoint/submit
PURCHASE_WORKER_URL=https://your-worker.example.com/v1/purchase/review
```

Worker:

```env
BROWSERBASE_API_KEY=...
BROWSERBASE_PROJECT_ID=...
BROWSERBASE_CONTEXT_ID=...
BROWSERBASE_USE_PROXY=0
BROWSERBASE_PROXY_CITY=
BROWSERBASE_PROXY_STATE=
BROWSERBASE_PROXY_COUNTRY=
MODEL_API_KEY=...
STAGEHAND_MODEL_NAME=google/gemini-3-flash-preview
PURCHASE_MAX_TOTAL_USD=optional_default_guard
PURCHASE_WORKER_PORT=8003
```

The worker uses Stagehand for the browser automation. The Browserbase context must already be logged into Amazon with shipping and payment configured.

## Browserbase Context Setup

You need to create one persistent Browserbase context before live purchase tests will work:

1. In Browserbase, create a new browser context and copy its context ID.
2. Start a Browserbase session with that context using Live View.
3. Open the Live View URL and manually log into Amazon.
4. Complete any MFA, passkey, account challenge, or shipping/payment prompts by hand.
5. End the session so the context persists cookies, local storage, and Amazon login state.
6. Put the copied context ID in `.env` as `BROWSERBASE_CONTEXT_ID`.

The code starts every Stagehand session with:

```json
{
  "browserSettings": {
    "context": {
      "id": "BROWSERBASE_CONTEXT_ID",
      "persist": true
    }
  }
}
```

If `BROWSERBASE_USE_PROXY=1`, the code also sends proxy settings:

```json
{
  "proxies": [
    {
      "type": "browserbase",
      "geolocation": {
        "city": "New York",
        "state": "NY",
        "country": "US"
      }
    }
  ]
}
```

Only enable `BROWSERBASE_USE_PROXY` on a Browserbase plan that includes proxies. Change the `BROWSERBASE_PROXY_*` values if your Amazon account normally logs in from a different region. If Amazon asks for MFA during a run, open the Browserbase session recording/live view, complete the challenge, then rerun.

## Run Locally

```bash
uv sync
uv run purchase-worker
uv run purchase-agent
```

## Register on Agentverse

The agent supports the ASI:One Agent Chat Protocol and publishes its manifest on startup.

For a local mailbox registration, leave `AGENT_ENDPOINT` unset, run the agent, open the Agent Inspector URL printed in the logs, then click **Connect** and choose **Mailbox**. The initial `Agent mailbox not found` or mailbox `401` log is expected until that mailbox is created from the Inspector.

For the Agentverse **Launch an Agent -> Connect Agent -> Chat Protocol** flow, set `AGENT_ENDPOINT` to a public `/submit` URL that points at this running agent. Do not use `127.0.0.1` for Agentverse registration because Agentverse cannot reach your local loopback address.

Keep `AGENT_SEED` stable once registered. Changing it creates a different agent address.

Run tests:

```bash
uv run pytest
```

Run real Browserbase integration tests:

```bash
set LIVE_BROWSERBASE=1
set LIVE_PURCHASE_DESCRIPTION=USB-C charging cable 6ft
set LIVE_PURCHASE_MAX_PRICE=15
uv run pytest tests/test_browserbase_worker.py -m integration
```

Run the purchase-agent payload test against actual local Stagehand:

```bash
set LIVE_BROWSERBASE=1
uv run pytest tests/test_purchase_agent.py -m integration
```

## Request Shape

The agent accepts either JSON or natural language. JSON is preferred:

```json
{
  "description": "USB-C charging cable 6ft",
  "quantity": 1,
  "brand": "Anker",
  "max_price": 15,
  "required_features": ["braided"],
  "disallow_substitutes": true
}
```

## Safety

The Browserbase flow intentionally stops at checkout review. The implementation never clicks a final place-order button.


## Runnning it

```
cd flagship-skill
python agent.py
```

in separate terminal:

```
cd flagship-skill
uv run purchase-worker
```