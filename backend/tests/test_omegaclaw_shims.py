from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from omegaclaw.skills import shims  # noqa: E402


class OmegaClawShimsTests(unittest.TestCase):
    def test_classify_intent_identify_person(self) -> None:
        self.assertEqual(
            shims.classify_intent("Who is this person?", {}),
            "identify_person",
        )

    def test_invoke_local_skill_shim_delegates_to_bridge(self) -> None:
        async def _run() -> None:
            with patch("omegaclaw.skills.shims.invoke_remote_skill", return_value={"summary": "ok"}) as mocked:
                result = await shims.invoke_local_skill_shim(
                    skill_name="identify_person",
                    args={"name": "A"},
                )
                mocked.assert_awaited_once_with(skill_name="identify_person", args={"name": "A"})
                self.assertEqual(result["summary"], "ok")

        asyncio.run(_run())

    def test_dispatch_skill_supports_task_like_objects(self) -> None:
        class _Task:
            intent = "Who is this?"
            args = {"name": "Alex"}

        async def _run() -> None:
            with patch("omegaclaw.skills.shims.invoke_local_skill_shim", return_value={"summary": "ok"}) as mocked:
                await shims.dispatch_skill(_Task())
                mocked.assert_awaited_once_with(skill_name="identify_person", args={"name": "Alex"})

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
