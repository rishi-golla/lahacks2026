from __future__ import annotations

import json
import unittest

from people_finder.chat import parse_chat_request
from people_finder.harness import PeopleFinderHarness
from people_finder.models import IdentifyPersonRequest
from people_finder.settings import Settings


class ChatParsingTests(unittest.TestCase):
    def test_json_payload_maps_badge_fields(self) -> None:
        request = parse_chat_request(
            '{"name":"Neel Shanmugam","organization":"Cluely","title":"Co-Founder"}',
            max_results=5,
        )

        self.assertEqual(request.name, "Neel Shanmugam")
        self.assertEqual(request.organization, "Cluely")
        self.assertEqual(request.title, "Co-Founder")

    def test_natural_query_extracts_name_and_organization(self) -> None:
        request = parse_chat_request("Who is Neel Shanmugam from Cluely?", max_results=3)

        self.assertEqual(request.name, "Neel Shanmugam")
        self.assertEqual(request.organization, "Cluely")


class HarnessFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_people_search_logs_request_and_response(self) -> None:
        settings = Settings()
        harness = PeopleFinderHarness(settings)
        request = IdentifyPersonRequest(
            name="Neel Shanmugam",
            organization="Cluely",
            title="Co-Founder",
            max_results=settings.max_tool_results,
        )

        response = await harness.identify(request)

        print("\nidentify_person request:")
        print(json.dumps(request.model_dump(exclude_none=True), indent=2))
        print("identify_person response:")
        print(json.dumps(response.model_dump(mode="json", exclude_none=True), indent=2))

        self.assertTrue(response.summary)
        self.assertIn(response.confidence, {"high", "medium", "low"})
        self.assertTrue(response.tool_results)

    async def test_missing_name_is_low_confidence(self) -> None:
        harness = PeopleFinderHarness(Settings())

        response = await harness.identify(IdentifyPersonRequest(organization="Cluely"))

        self.assertEqual(response.confidence, "low")
        self.assertIn("name", response.summary.lower())


if __name__ == "__main__":
    unittest.main()
