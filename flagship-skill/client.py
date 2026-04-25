from __future__ import annotations

import argparse
import asyncio

import httpx
from uagents import Agent, Context, Model


class IdentifyPersonQuery(Model):
    name: str | None = None
    organization: str | None = None
    title: str | None = None
    domain: str | None = None
    location: str | None = None


class IdentifyPersonResult(Model):
    summary: str
    confidence: str
    source: str


async def call_bridge(args: argparse.Namespace) -> None:
    payload = {
        "name": args.name,
        "organization": args.organization,
        "title": args.title,
        "domain": args.domain,
        "location": args.location,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(f"{args.bridge_url.rstrip('/')}/identify_person", json=payload)
        response.raise_for_status()
        print(response.json())


def call_agent(args: argparse.Namespace) -> None:
    if not args.address:
        raise SystemExit("--address is required for agent mode")
    if not args.seed:
        raise SystemExit("--seed is required for agent mode")

    client = Agent(name="identify-person-client", seed=args.seed, port=args.port)

    @client.on_event("startup")
    async def send_query(ctx: Context) -> None:
        reply, status = await ctx.send_and_receive(
            args.address,
            IdentifyPersonQuery(
                name=args.name,
                organization=args.organization,
                title=args.title,
                domain=args.domain,
                location=args.location,
            ),
            response_type=IdentifyPersonResult,
            timeout=20,
        )
        if isinstance(reply, IdentifyPersonResult):
            ctx.logger.info(
                "summary=%s confidence=%s source=%s",
                reply.summary,
                reply.confidence,
                reply.source,
            )
        else:
            ctx.logger.error("query failed status=%s", status)
        ctx.logger.info("client query complete; press Ctrl+C to stop the smoke client")

    client.run()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test the identify_person skill.")
    parser.add_argument("--mode", choices=["bridge", "agent"], default="bridge")
    parser.add_argument("--bridge-url", default="http://127.0.0.1:8003")
    parser.add_argument("--address", help="Remote identify_person agent address")
    parser.add_argument("--seed", help="Client agent seed for Agentverse mode")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--name", required=True)
    parser.add_argument("--organization")
    parser.add_argument("--title")
    parser.add_argument("--domain")
    parser.add_argument("--location")
    return parser.parse_args()


if __name__ == "__main__":
    parsed_args = parse_args()
    if parsed_args.mode == "bridge":
        asyncio.run(call_bridge(parsed_args))
    else:
        call_agent(parsed_args)
