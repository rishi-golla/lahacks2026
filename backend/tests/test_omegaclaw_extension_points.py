from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from omegaclaw.channels import my_backend  # noqa: E402
from omegaclaw.remote import agentverse_bridge  # noqa: E402


class OmegaClawExtensionPointTests(unittest.TestCase):
    def test_channel_adapter_contract_functions_exist(self) -> None:
        self.assertTrue(callable(my_backend.start_my_backend))
        self.assertTrue(callable(my_backend.getLastMessage))
        self.assertTrue(callable(my_backend.send_message))

    def test_remote_bridge_entrypoints_exist(self) -> None:
        self.assertTrue(callable(agentverse_bridge.invoke_remote_skill))
        self.assertTrue(callable(agentverse_bridge.invoke_identify_person))
        self.assertTrue(callable(agentverse_bridge.invoke_describe_scene))
        self.assertTrue(callable(agentverse_bridge.invoke_google_search))
        self.assertTrue(callable(agentverse_bridge.invoke_google_calendar))
        self.assertTrue(callable(agentverse_bridge.invoke_gmail))
        self.assertTrue(callable(agentverse_bridge.invoke_people_search_agent))
        self.assertTrue(callable(agentverse_bridge.invoke_mail_sending_agent))
        self.assertTrue(callable(agentverse_bridge.invoke_task_scheduling_agent))
        self.assertTrue(callable(agentverse_bridge.invoke_reminder_agent))
        self.assertTrue(callable(agentverse_bridge.invoke_purchase_agent))

    def test_channels_metta_contains_required_wiring(self) -> None:
        content = (REPO_ROOT / "omegaclaw" / "src" / "channels.metta").read_text(encoding="utf-8")
        self.assertIn("(= (MY_BACKEND_URL) (empty))", content)
        self.assertIn("(= (MY_BACKEND_SECRET) (empty))", content)
        self.assertIn("(= (MY_BACKEND_POLL_MS) (empty))", content)
        self.assertIn("(= (initChannels)", content)
        self.assertIn("(= (receive)", content)
        self.assertIn("(= (send $msg)", content)
        self.assertIn("(my_backend.start_my_backend", content)
        self.assertIn("(my_backend.getLastMessage)", content)
        self.assertIn("(my_backend.send_message $msg)", content)

    def test_skills_metta_contains_flagship_and_registration_surface(self) -> None:
        content = (REPO_ROOT / "omegaclaw" / "src" / "skills.metta").read_text(encoding="utf-8")
        self.assertIn("(= (getSkills)", content)
        self.assertIn("identify-person", content)
        self.assertIn("google-search", content)
        self.assertIn("google-calendar", content)
        self.assertIn("people-search-agent", content)
        self.assertIn("mail-sending-agent", content)
        self.assertIn("task-scheduling-agent", content)
        self.assertIn("reminder-agent", content)
        self.assertIn("purchase-agent", content)
        self.assertIn("(= (identify-person $name $organization $title)", content)
        self.assertIn("(agentverse_bridge.invoke_identify_person", content)
        self.assertIn("(agentverse_bridge.invoke_people_search_agent", content)


if __name__ == "__main__":
    unittest.main()
