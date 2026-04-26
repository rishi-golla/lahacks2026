#!/usr/bin/env python3
"""OmegaClaw + BackendChannel integration diagnostics (no Gemini API calls).

Helps debug cases like "set a reminder in 5 seconds" where the model may say
"sure" but nothing happens: often the model never calls `agent`, calls it with
an intent that does not route to calendar, or the skill layer returns a
failure/fallback summary that the model still glosses over.

Run from repo root (recommended):

  cd backend && uv run python ../scripts/omegaclaw_agent_tool_integration.py

  cd backend && uv run python ../scripts/omegaclaw_agent_tool_integration.py --slow-remote 2.0

Environment:
  Leave OMEGACLAW_URL unset for local channel-loop mode. If it is set, this script
  prints a note and exercises the gateway path instead.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (str(REPO_ROOT), str(REPO_ROOT / "backend")):
    if p not in sys.path:
        sys.path.insert(0, p)

from omegaclaw.channels.backend_channel import BackendChannel, GlassesTask  # noqa: E402
from omegaclaw.runtime_loop import OmegaClawAgentLoop  # noqa: E402


def _live_adapter_style_summary(result: dict[str, Any]) -> str:
    """Same extraction as GeminiLiveAdapter._handle_agent_tool_call."""
    return (
        result.get("summary")
        or result.get("description")
        or str(result)
    )


def _print_case(title: str, task: GlassesTask, result: dict[str, Any], elapsed_s: float) -> None:
    gemini_output = _live_adapter_style_summary(result)
    print(f"\n=== {title} ===")
    print(f"  intent={task.intent!r} args={task.args!r}")
    print(f"  elapsed_s={elapsed_s:.3f}")
    print(f"  full_result={result!r}")
    print(f"  string_sent_back_to_gemini_as_tool_output={gemini_output!r}")


async def _submit(task: GlassesTask) -> dict[str, Any]:
    channel = BackendChannel()
    return await channel.submit(task)


def _classify_samples() -> None:
    classify = OmegaClawAgentLoop._classify
    samples = [
        "set a reminder for me in 5 seconds",
        "remind me in 5 seconds",
        "add a meeting to my calendar tomorrow at 3pm",
        "schedule an event next Tuesday",
        "google search for coffee shops",
        "identify_person",
    ]
    print("OmegaClawAgentLoop._classify(intent, {}) — reminder wording is NOT mapped to google_calendar today:")
    for s in samples:
        skill = classify(s, {})
        print(f"  {s!r} -> {skill!r}")


async def _run_cases(*, slow_remote_s: float | None) -> None:
    if os.environ.get("OMEGACLAW_URL"):
        print(
            "NOTE: OMEGACLAW_URL is set — BackendChannel uses the gateway passthrough path, "
            "not the local my_backend + OmegaClawAgentLoop path.\n"
        )
    _classify_samples()

    tasks: list[tuple[str, GlassesTask]] = [
        (
            "User-style reminder (intent string only — typical no_match)",
            GlassesTask(
                session_id="integ-session",
                turn_id="turn-1",
                intent="set a reminder for me in 5 seconds",
                tool_call_id="call-reminder",
                args={},
            ),
        ),
        (
            "Calendar-ish intent (routes to google_calendar; no endpoint in skill JSON -> immediate fallback)",
            GlassesTask(
                session_id="integ-session",
                turn_id="turn-2",
                intent="add this to my calendar tomorrow at 9am",
                tool_call_id="call-cal",
                args={"query": "team sync"},
            ),
        ),
        (
            "Explicit skill_name in args (still hits remote path for google_calendar)",
            GlassesTask(
                session_id="integ-session",
                turn_id="turn-3",
                intent="anything",
                tool_call_id="call-cal2",
                args={
                    "skill_name": "google_calendar",
                    "command": "create",
                    "datetime": "in 5 seconds",
                    "details": "integration test reminder",
                },
            ),
        ),
    ]

    remote_patch_cm = None
    if slow_remote_s is not None:
        delay = slow_remote_s

        async def _slow_remote(skill_name: str, args: dict) -> dict:
            await asyncio.sleep(delay)
            return {
                "summary": f"mock remote finished for {skill_name} args={args!r}",
                "confidence": "high",
                "source": "mock:integration_script",
            }

        remote_patch_cm = patch(
            "omegaclaw.runtime_loop.invoke_remote_skill",
            new=_slow_remote,
        )
        remote_patch_cm.__enter__()
        print(f"\n(patch) invoke_remote_skill sleeps {delay}s then returns success — watch elapsed_s.")

    try:
        for title, task in tasks:
            t0 = time.perf_counter()
            result = await _submit(task)
            elapsed = time.perf_counter() - t0
            _print_case(title, task, result, elapsed)
    finally:
        if remote_patch_cm is not None:
            remote_patch_cm.__exit__(None, None, None)


async def _run_live_adapter_smoke(*, slow_remote_s: float) -> None:
    """Prove GeminiLiveAdapter awaits BackendChannel.submit before send_tool_response."""
    from types import SimpleNamespace

    from app.session.coordinator import SessionContext
    from app.session.live_adapter import GeminiLiveAdapter
    from app.session.settings import LiveBackend, SessionSettings

    sent: list[tuple[str, float]] = []

    class _FakeLiveSession:
        def __init__(self) -> None:
            self.tool_response_calls: list[Any] = []

        async def send_tool_response(self, *, function_responses: list[Any]) -> None:
            self.tool_response_calls.append(function_responses)
            sent.append(("tool_response", time.perf_counter()))

    async def _slow_submit(_task: GlassesTask) -> dict[str, Any]:
        sent.append(("submit_start", time.perf_counter()))
        await asyncio.sleep(slow_remote_s)
        sent.append(("submit_end", time.perf_counter()))
        return {"summary": "calendar mock ok", "confidence": "high", "source": "mock"}

    settings = SessionSettings.model_validate(
        {
            "live_backend": LiveBackend.GEMINI,
            "gemini_api_key": "test-key-for-script",
        }
    )
    fake_session = _FakeLiveSession()
    adapter = GeminiLiveAdapter(
        settings,
        client_factory=lambda **_: SimpleNamespace(),
    )
    adapter._live_session = fake_session

    mock_bc = MagicMock()
    mock_bc.submit = AsyncMock(side_effect=_slow_submit)
    adapter._backend_channel = mock_bc

    sender = _FakeSender()
    t0 = time.perf_counter()
    await adapter._handle_agent_tool_call(
        "call-live-1",
        {"intent": "schedule a meeting tomorrow", "name": "x"},
        sender,
        SessionContext(session_id="sess-live"),
    )
    total = time.perf_counter() - t0

    assert fake_session.tool_response_calls, "expected send_tool_response"
    order = [x[0] for x in sent]
    print("\n=== GeminiLiveAdapter._handle_agent_tool_call ordering ===")
    print(f"  events={order}")
    print(f"  total_elapsed_s={total:.3f} (should be >= slow_remote_s={slow_remote_s})")
    if order != ["submit_start", "submit_end", "tool_response"]:
        print("  WARNING: expected submit_start, submit_end, then tool_response")


class _FakeSender:
    async def send(self, _msg: dict[str, Any]) -> None:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slow-remote",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Patch invoke_remote_skill to sleep N seconds then succeed (proves channel awaits).",
    )
    parser.add_argument(
        "--live-adapter-ordering",
        action="store_true",
        help="Smoke-test that GeminiLiveAdapter awaits BackendChannel before send_tool_response.",
    )
    parser.add_argument(
        "--adapter-sleep",
        type=float,
        default=0.4,
        help="Sleep injected into mocked BackendChannel.submit for --live-adapter-ordering.",
    )
    args = parser.parse_args()

    if args.live_adapter_ordering:
        asyncio.run(_run_live_adapter_smoke(slow_remote_s=args.adapter_sleep))
    else:
        asyncio.run(_run_cases(slow_remote_s=args.slow_remote))


if __name__ == "__main__":
    main()
