import os
from uagents import Agent, Context, Model
from context_service import get_person_context


class PersonQuery(Model):
    name: str
    organization: str
    title: str = ""


class PersonContext(Model):
    summary: str
    confidence: str  # 'high' or 'low'
    source: str = "gemini"


agent = Agent(
    name="contextlens-person-intelligence",
    seed=os.environ.get("AGENT_SEED", "contextlens-default-seed-2026"),
    port=8001,
    endpoint=["http://localhost:8001/submit"],
)


@agent.on_message(model=PersonQuery)
async def handle_person_query(ctx: Context, sender: str, msg: PersonQuery):
    ctx.logger.info(f"Received person query for {msg.name} at {msg.organization}")
    result = await get_person_context(msg.name, msg.organization, msg.title)
    response = PersonContext(
        summary=result["summary"],
        confidence=result["confidence"],
        source=result["source"],
    )
    await ctx.send(sender, response)


if __name__ == "__main__":
    agent.run()
