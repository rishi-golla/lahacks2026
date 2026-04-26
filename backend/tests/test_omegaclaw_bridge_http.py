from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest
from pathlib import Path

from httpx import ASGITransport, AsyncClient


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))


class OmegaClawBridgeHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._prev_bridge = os.environ.get("OMEGACLAW_BRIDGE_ENABLED")
        self._prev_secret = os.environ.get("OMEGACLAW_BRIDGE_SECRET")
        self._prev_smoke = os.environ.get("OMEGACLAW_BRIDGE_SMOKE")
        os.environ["OMEGACLAW_BRIDGE_ENABLED"] = "1"
        os.environ.pop("OMEGACLAW_BRIDGE_SECRET", None)
        os.environ.pop("OMEGACLAW_BRIDGE_SMOKE", None)

    async def asyncTearDown(self) -> None:
        if self._prev_bridge is None:
            os.environ.pop("OMEGACLAW_BRIDGE_ENABLED", None)
        else:
            os.environ["OMEGACLAW_BRIDGE_ENABLED"] = self._prev_bridge
        if self._prev_secret is None:
            os.environ.pop("OMEGACLAW_BRIDGE_SECRET", None)
        else:
            os.environ["OMEGACLAW_BRIDGE_SECRET"] = self._prev_secret
        if self._prev_smoke is None:
            os.environ.pop("OMEGACLAW_BRIDGE_SMOKE", None)
        else:
            os.environ["OMEGACLAW_BRIDGE_SMOKE"] = self._prev_smoke

        from app import omegaclaw_bridge as ob

        ob._queue = None  # type: ignore[attr-defined]
        ob._waiters.clear()

    async def test_next_returns_task_line_after_enqueue(self) -> None:
        from app import omegaclaw_bridge as ob
        from app.main import app

        job = {"request_id": "rid-test", "intent": "ping", "args": {}}

        async def producer() -> None:
            await asyncio.sleep(0.05)
            await ob._queue_get().put(job)

        asyncio.create_task(producer())

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/internal/omegaclaw/next")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.startswith("LAHACKS_TASK_JSON:"))
        payload = json.loads(r.text.split(":", 1)[1])
        self.assertEqual(payload["request_id"], "rid-test")

    async def test_result_unblocks_enqueue(self) -> None:
        from app import omegaclaw_bridge as ob

        async def complete_later() -> None:
            await asyncio.sleep(0.05)
            ok = ob.complete_from_result(
                "rid-2",
                json.dumps(
                    {
                        "request_id": "rid-2",
                        "result": {"summary": "done", "confidence": "high", "source": "test"},
                    }
                ),
            )
            self.assertTrue(ok)

        asyncio.create_task(complete_later())
        out = await ob.enqueue_and_wait({"request_id": "rid-2", "intent": "x"}, timeout_s=2.0)
        self.assertEqual(out["result"]["summary"], "done")

    async def test_backend_channel_round_trips_through_http_bridge(self) -> None:
        from app.main import app
        from omegaclaw.channels.backend_channel import BackendChannel, GlassesTask

        submit_task = asyncio.create_task(
            BackendChannel().submit(
                GlassesTask(
                    session_id="session-rt",
                    turn_id="turn-rt",
                    intent="lahacks echo smoke",
                    tool_call_id="call-rt",
                    args={"skill_name": "lahacks_echo", "text": "hello"},
                )
            )
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            next_response = await client.get("/internal/omegaclaw/next")
            self.assertEqual(next_response.status_code, 200)
            self.assertTrue(next_response.text.startswith("LAHACKS_TASK_JSON:"))
            job = json.loads(next_response.text.split(":", 1)[1])
            self.assertEqual(job["session_id"], "session-rt")
            self.assertEqual(job["tool_call_id"], "call-rt")
            self.assertIn("request_id", job)

            result_text = json.dumps(
                {
                    "request_id": job["request_id"],
                    "result": {
                        "summary": "round trip done",
                        "confidence": "high",
                        "source": "test:http_bridge",
                    },
                }
            )
            result_response = await client.post(
                "/internal/omegaclaw/result",
                json={"request_id": job["request_id"], "text": result_text},
            )
            self.assertEqual(result_response.status_code, 200)
            self.assertEqual(result_response.json(), {"ok": True})

        result = await asyncio.wait_for(submit_task, timeout=2.0)
        self.assertEqual(result["summary"], "round trip done")
        self.assertEqual(result["source"], "test:http_bridge")

    async def test_enqueue_and_wait_returns_busy_when_request_in_flight(self) -> None:
        from app import omegaclaw_bridge as ob

        first = asyncio.create_task(
            ob.enqueue_and_wait({"request_id": "rid-busy-1", "intent": "first"}, timeout_s=5.0)
        )
        for _ in range(20):
            if ob._waiters:  # type: ignore[attr-defined]
                break
            await asyncio.sleep(0.01)
        self.assertIn("rid-busy-1", ob._waiters)  # type: ignore[attr-defined]

        second = await ob.enqueue_and_wait(
            {"request_id": "rid-busy-2", "intent": "second"},
            timeout_s=5.0,
        )
        self.assertEqual(second["result"]["error"], "bridge_busy")

        first.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await first

    async def test_smoke_submit_returns_404_when_disabled(self) -> None:
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post("/internal/omegaclaw/smoke-submit")
        self.assertEqual(r.status_code, 404)

    async def test_smoke_submit_round_trips_through_http_bridge(self) -> None:
        os.environ["OMEGACLAW_BRIDGE_SMOKE"] = "1"
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", timeout=30.0) as client:
            smoke_task = asyncio.create_task(client.post("/internal/omegaclaw/smoke-submit"))
            await asyncio.sleep(0.08)
            next_response = await client.get("/internal/omegaclaw/next")
            self.assertEqual(next_response.status_code, 200)
            self.assertTrue(next_response.text.startswith("LAHACKS_TASK_JSON:"))
            job = json.loads(next_response.text.split(":", 1)[1])
            result_text = json.dumps(
                {
                    "request_id": job["request_id"],
                    "result": {
                        "summary": "smoke via endpoint",
                        "confidence": "high",
                        "source": "test:smoke_submit",
                    },
                }
            )
            result_response = await client.post(
                "/internal/omegaclaw/result",
                json={"request_id": job["request_id"], "text": result_text},
            )
            self.assertEqual(result_response.status_code, 200)
            smoke_response = await asyncio.wait_for(smoke_task, timeout=5.0)

        self.assertEqual(smoke_response.status_code, 200)
        body = smoke_response.json()
        self.assertTrue(body.get("ok"))
        self.assertEqual(body["result"]["summary"], "smoke via endpoint")
        self.assertEqual(body["result"]["source"], "test:smoke_submit")
