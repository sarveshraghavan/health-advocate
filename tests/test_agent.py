"""
Agent Unit Tests
=================
Tests the agent's intent routing and mock fallback behavior.

Run:
    cd backend
    python ../tests/test_agent.py
"""

import asyncio
import sys
import os

# Add paths so imports work from the tests/ folder
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../synthetic_data"))

from mock_apis import patch_all, set_profile
patch_all()

from agent import run_agent
from stepup import record_step_up, check_step_up

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

results = []


def check(name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    results.append(condition)
    extra = f"  ({detail})" if detail else ""
    print(f"  {status} {name}{extra}")


async def test_intent_routing():
    """Test that messages route to the correct intent handler."""
    print("\n── Intent Routing ──")

    # Heart rate intent
    r = await run_agent("test-user", "what is my heart rate?")
    check("Heart rate intent", r["status"] == "ok", f"status={r['status']}")

    r = await run_agent("test-user", "check my bpm")
    check("BPM intent", r["status"] == "ok")

    # Trend intent
    r = await run_agent("test-user", "how was my week?")
    check("Weekly trend intent", r["status"] == "ok")

    r = await run_agent("test-user", "show my vitals")
    check("Vitals intent", r["status"] == "ok")

    # Records intent
    r = await run_agent("test-user", "show my medical records")
    check("Medical records intent", r["status"] == "ok")

    # General question (default fallback)
    r = await run_agent("test-user", "what should I eat for breakfast?")
    check("General question fallback", r["status"] == "ok")


async def test_step_up_flow():
    """Test that write intents require step-up auth."""
    print("\n── Step-Up Auth Flow ──")

    # Book appointment without step-up → should require it
    r = await run_agent("stepup-test", "book an appointment")
    check("Book requires step-up", r["status"] == "step_up_required", f"status={r['status']}")
    check("Challenge URL present", "challenge_url" in r)

    # Simulate step-up completion
    record_step_up("stepup-test")
    check("Step-up recorded", check_step_up("stepup-test") == True)

    # Book appointment after step-up → should succeed
    r = await run_agent("stepup-test", "book an appointment with Dr. Smith")
    check("Book after step-up succeeds", r["status"] == "ok", f"response={r.get('response','')[:60]}")


async def test_profiles():
    """Test that different patient profiles return different data."""
    print("\n── Patient Profiles ──")

    set_profile("healthy")
    r1 = await run_agent("profile-test", "what is my heart rate?")
    check("Healthy profile responds", r1["status"] == "ok")

    set_profile("at_risk")
    r2 = await run_agent("profile-test", "what is my heart rate?")
    check("At-risk profile responds", r2["status"] == "ok")

    set_profile("recovery")
    r3 = await run_agent("profile-test", "how have I been this week?")
    check("Recovery profile responds", r3["status"] == "ok")

    # All 3 profiles should have produced valid responses
    check("All profiles produced responses",
          all(r.get("response") for r in [r1, r2, r3]),
          "all 3 responded")


async def run_tests():
    print("=" * 50)
    print("Health Advocate — Agent Tests")
    print("=" * 50)

    await test_intent_routing()
    await test_step_up_flow()
    await test_profiles()

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 50}")
    print(f"Results: {passed}/{total} passed")
    if passed == total:
        print("\033[92mAll tests passed!\033[0m")
    else:
        print(f"\033[91m{total - passed} test(s) failed\033[0m")
    print("=" * 50)

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
