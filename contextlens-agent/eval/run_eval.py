"""
Evaluation runner for the ContextLens identify_person skill.

Usage:
    python eval/run_eval.py
"""

import asyncio
import json
import os
import sys

# Allow importing from the parent contextlens-agent directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from context_service import get_person_context


FIXTURES_PATH = os.path.join(os.path.dirname(__file__), "fixtures.json")

COL_CASE = 30
COL_NAME = 20
COL_CONF = 12
COL_EXP = 12
COL_RESULT = 10


def _row(case, name, confidence, expected, passed):
    result_str = "PASS" if passed else "FAIL"
    return (
        f"{case:<{COL_CASE}} "
        f"{name:<{COL_NAME}} "
        f"{confidence:<{COL_CONF}} "
        f"{expected:<{COL_EXP}} "
        f"{result_str:<{COL_RESULT}}"
    )


async def run_eval():
    with open(FIXTURES_PATH) as f:
        fixtures = json.load(f)

    header = (
        f"{'case':<{COL_CASE}} "
        f"{'name':<{COL_NAME}} "
        f"{'confidence':<{COL_CONF}} "
        f"{'expected':<{COL_EXP}} "
        f"{'result':<{COL_RESULT}}"
    )
    separator = "-" * len(header)

    print(header)
    print(separator)

    passes = 0
    total = len(fixtures)

    for fixture in fixtures:
        case = fixture["case"]
        name = fixture["name"]
        org = fixture["org"]
        title = fixture["title"]
        expected = fixture["expected_confidence"]

        result = await get_person_context(name, org, title)
        confidence = result["confidence"]
        passed = confidence == expected
        if passed:
            passes += 1

        print(_row(case, name or "(empty)", confidence, expected, passed))

    print(separator)
    print(f"\nResults: {passes}/{total} passed")
    if passes < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_eval())
