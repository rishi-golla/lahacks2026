import asyncio

from uagents import Agent
from uagents_adapter import MCPServerAdapter

from server import mcp

ASI1_API_KEY = "sk_ad6517b8b7974ad58e5ae456b122c38d82c5c57d06e242169733e74653b1f96d"
ASI1_MODEL = "asi1"
AGENT_NAME = "playwright-agent"
AGENT_PORT = 8000
AGENT_SEED = "seed_phrase_lol"

try:
    asyncio.get_event_loop_policy().get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Create an MCP adapter with your Playwright MCP server wrapper
mcp_adapter = MCPServerAdapter(
    mcp_server=mcp,
    asi1_api_key=ASI1_API_KEY,
    model=ASI1_MODEL,
)

# Create a uAgent
agent = Agent(
    name=AGENT_NAME,
    port=AGENT_PORT,
    seed=AGENT_SEED,
    mailbox=True,
)

# Include protocols from the adapter
for protocol in mcp_adapter.protocols:
    agent.include(protocol, publish_manifest=True)


if __name__ == "__main__":
    mcp_adapter.run(agent)
