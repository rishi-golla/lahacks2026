# ASI:One Playwright MCP Purchase Agent

This package contains a standalone ASI:One-compatible Agentverse agent for product purchasing assistance. It accepts product metadata, asks Gemini to drive a local browser through the stock Playwright MCP server, searches Amazon, adds the selected match to cart, and stops at checkout review.

It does not place orders.

## Files

- `agent.py` - ASI:One Agent Chat Protocol agent for Agentverse upload.
- `purchase_client.py` - Playwright MCP HTTP client plus Gemini tool loop.
- `purchase_prompt.py` - browser workflow and safety prompt.
- `purchase_rules.py` - deterministic query/candidate helper rules.
- `models.py` - typed request/result models.

## Environment

```env
AGENT_SEED=replace-with-agent-seed
AGENT_PORT=8001
AGENT_ENDPOINT=https://your-public-agent-endpoint/submit

PLAYWRIGHT_MCP_URL=http://127.0.0.1:8931/mcp
PLAYWRIGHT_MCP_TIMEOUT_S=180

GEMINI_API_KEY=replace-with-gemini-api-key
PURCHASE_AGENT_MODEL=gemini-2.5-flash

AMAZON_URL=https://www.amazon.com
PURCHASE_MAX_TOTAL_USD=
```

`MODEL_API_KEY` is still accepted as a fallback for the Gemini key so older local `.env` files keep working.

## Local Browser Setup

Start the stock Playwright MCP server in a separate terminal:

```powershell
npx @playwright/mcp@latest --port 8931 --browser=chrome
```

Playwright MCP owns the browser automation surface. This package does not define custom MCP tools such as `get_products` or `buy_product`; the purchase workflow lives in the agent prompt and uses the generic Playwright MCP tools.

By default, Playwright MCP runs in headed mode with a persistent profile. Sign in to Amazon in that browser profile before asking the agent to prepare a checkout review.

## Run Locally

```bash
uv sync
uv run purchase-agent
```

If `uv` cannot access its global cache on Windows, use the existing virtualenv directly:

```powershell
.\.venv\Scripts\python.exe agent.py
```

## Register on Agentverse

The agent supports the ASI:One Agent Chat Protocol and publishes its manifest on startup.

For a local mailbox registration, leave `AGENT_ENDPOINT` unset, run the agent, open the Agent Inspector URL printed in the logs, then click **Connect** and choose **Mailbox**. The initial `Agent mailbox not found` or mailbox `401` log is expected until that mailbox is created from the Inspector.

For the Agentverse **Launch an Agent -> Connect Agent -> Chat Protocol** flow, set `AGENT_ENDPOINT` to a public `/submit` URL that points at this running agent. Do not use `127.0.0.1` for Agentverse registration because Agentverse cannot reach your local loopback address.

Keep `AGENT_SEED` stable once registered. Changing it creates a different agent address.

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

## Tests

```bash
uv run pytest
```

Run the live Playwright MCP smoke test only when the MCP HTTP server is already running:

```powershell
$env:LIVE_PLAYWRIGHT_MCP="1"
$env:PLAYWRIGHT_MCP_URL="http://127.0.0.1:8931/mcp"
.\.venv\Scripts\python.exe -m pytest tests/test_purchase_mcp_server.py -m integration
```

## Safety

The local browser flow intentionally stops at checkout review. The prompt explicitly forbids placing, submitting, completing, confirming, or finalizing an order.
