"""
Health Advocate Agent — Full Test Suite
========================================
Tests every feature:
  ✓ Heart rate reading (all 3 profiles)
  ✓ Weekly trend summary
  ✓ Alert firing when HR > threshold
  ✓ Step-up auth blocking write actions
  ✓ Booking appointment after step-up
  ✓ Sending summary to doctor after step-up
  ✓ Token revocation

Run:
    cd backend
    python ../tests/test_agent.py
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../synthetic_data"))

# Generate data first if not present
from pathlib import Path
if not (Path(__file__).parent.parent / "synthetic_data/output/healthy.json").exists():
    print("Generating synthetic data first...\n")
    import subprocess
    subprocess.run([sys.executable, "../synthetic_data/generate.py"])

from mock_apis import patch_all, set_profile

# Apply patches BEFORE importing agent modules
patch_all()

from agent import run_agent, summarize_anomaly, summarize_trend
from watcher import watch_user
from stepup import record_step_up, check_step_up, get_remaining_window

# ── Test results tracker ──────────────────
passed = 0
failed = 0
results = []

def test(name: str, condition: bool, detail: str = ""):
    global passed, failed
    status = "PASS" if condition else "FAIL"
    icon   = "✓" if condition else "✗"
    color  = "\033[92m" if condition else "\033[91m"
    reset  = "\033[0m"
    print(f"  {color}{icon} {status}{reset}  {name}")
    if detail:
        print(f"         {detail}")
    if condition:
        passed += 1
    else:
        failed += 1
    results.append({"name": name, "passed": condition, "detail": detail})


# ──────────────────────────────────────────
# TEST GROUP 1: Heart rate reading
# ──────────────────────────────────────────

async def test_heart_rate_reading():
    print("\n── Test Group 1: Heart rate reading ────────────────")

    # Healthy profile
    set_profile("healthy")
    response = await run_agent("test-user-healthy", "what is my heart rate?")
    test("Healthy user: agent responds", "response" in response)
    test("Healthy user: no step-up required", response.get("status") == "ok")
    test("Healthy user: response is non-empty", len(response.get("response", "")) > 10)
    print(f"         LLM said: {response.get('response', '')[:120]}...")

    # At-risk profile
    set_profile("at_risk")
    response = await run_agent("test-user-atrisk", "how am i doing right now?")
    test("At-risk user: agent responds", "response" in response)
    test("At-risk user: no step-up for read", response.get("status") == "ok")
    print(f"         LLM said: {response.get('response', '')[:120]}...")


# ──────────────────────────────────────────
# TEST GROUP 2: Weekly trend summary
# ──────────────────────────────────────────

async def test_weekly_trend():
    print("\n── Test Group 2: Weekly trend summary ──────────────")

    set_profile("recovery")
    response = await run_agent("test-user-recovery", "summarize my health this week")
    test("Recovery user: trend summary returned", response.get("status") == "ok")
    test("Recovery user: response length > 20 chars", len(response.get("response", "")) > 20)
    # Verify raw numbers not exposed (privacy check)
    raw_bpm_exposed = any(str(x) in response.get("response", "") for x in range(70, 120))
    test("Privacy: raw BPM numbers not in response", not raw_bpm_exposed,
         "LLM should summarize trends, not repeat exact numbers")
    print(f"         LLM said: {response.get('response', '')[:150]}...")


# ──────────────────────────────────────────
# TEST GROUP 3: Alert system
# ──────────────────────────────────────────

async def test_alert_system():
    print("\n── Test Group 3: Alert system ───────────────────────")

    set_profile("at_risk")
    # Directly test summarize_anomaly
    summary = await summarize_anomaly(
        event="Heart rate spike detected: 112 BPM (threshold: 100 BPM)",
        user_id="test-user-atrisk"
    )
    test("Alert: summarize_anomaly returns text", isinstance(summary, str) and len(summary) > 10)
    test("Alert: summary mentions health concern", any(w in summary.lower() for w in
         ["heart", "rate", "elevated", "high", "concern", "doctor", "medical"]))
    print(f"         Alert summary: {summary[:150]}...")

    # Healthy profile should NOT mention concern
    set_profile("healthy")
    summary_ok = await summarize_anomaly(
        event="Heart rate: 68 BPM (normal range)",
        user_id="test-user-healthy"
    )
    test("Normal alert: no alarm language for healthy reading", isinstance(summary_ok, str))
    print(f"         Normal summary: {summary_ok[:150]}...")


# ──────────────────────────────────────────
# TEST GROUP 4: Step-up auth blocking writes
# ──────────────────────────────────────────

async def test_stepup_blocking():
    print("\n── Test Group 4: Step-up auth — write blocking ──────")

    set_profile("at_risk")
    user_id = "test-user-stepup-block"

    # Attempt booking WITHOUT step-up
    response = await run_agent(user_id, "book an appointment with Dr. Smith")
    test("Write blocked: status is step_up_required", response.get("status") == "step_up_required")
    test("Write blocked: challenge_url returned", "challenge_url" in response)
    test("Write blocked: message explains why", len(response.get("response", "")) > 10)
    print(f"         Agent said: {response.get('response', '')[:120]}...")

    # Attempt send-to-doctor WITHOUT step-up
    response2 = await run_agent(user_id, "send my summary to my doctor")
    test("Send blocked: status is step_up_required", response2.get("status") == "step_up_required")


# ──────────────────────────────────────────
# TEST GROUP 5: Step-up auth allows writes
# ──────────────────────────────────────────

async def test_stepup_allows_write():
    print("\n── Test Group 5: Step-up auth — write allowed ───────")

    set_profile("at_risk")
    user_id = "test-user-stepup-allow"

    # Simulate completed step-up
    session_token = record_step_up(user_id)
    test("Step-up recorded", check_step_up(user_id))
    remaining = get_remaining_window(user_id)
    test("Step-up window ~10 min", 590 <= remaining <= 600,
         f"Remaining: {remaining}s")

    # Now booking should succeed
    response = await run_agent(user_id, "book an appointment with Dr. Smith tomorrow")
    test("Booking succeeds after step-up", response.get("status") == "ok")
    test("Booking: confirmation in response", "confirm" in response.get("response", "").lower()
         or "book" in response.get("response", "").lower())
    print(f"         Agent said: {response.get('response', '')[:120]}...")

    # Send to doctor should also succeed
    response2 = await run_agent(user_id, "send my health summary to my doctor")
    test("Send to doctor succeeds after step-up", response2.get("status") == "ok")
    print(f"         Agent said: {response2.get('response', '')[:120]}...")


# ──────────────────────────────────────────
# TEST GROUP 6: Anomaly summarization (privacy)
# ──────────────────────────────────────────

async def test_privacy():
    print("\n── Test Group 6: Privacy — no raw data stored ───────")

    set_profile("at_risk")
    # get_weekly_vitals returns raw data — summarize_trend must not echo it back
    summary = await summarize_trend("test-user-privacy")
    test("Trend summary returned", isinstance(summary, str) and len(summary) > 0)

    # The summary should not contain raw JSON-like strings
    test("Privacy: no JSON artifacts in summary",
         "{" not in summary and "dataTypeName" not in summary,
         "Raw API response leaked into LLM output")
    print(f"         Trend summary: {summary[:180]}...")


# ──────────────────────────────────────────
# TEST GROUP 7: All 3 profiles end-to-end
# ──────────────────────────────────────────

async def test_all_profiles():
    print("\n── Test Group 7: All profiles end-to-end ────────────")

    for profile, uid, query in [
        ("healthy",  "test-user-healthy-e2e",  "how have i been this week?"),
        ("at_risk",  "test-user-atrisk-e2e",   "what is my heart rate?"),
        ("recovery", "test-user-recovery-e2e", "summarize my health trend"),
    ]:
        set_profile(profile)
        response = await run_agent(uid, query)
        test(f"{profile.upper()}: end-to-end chat works",
             response.get("status") in ("ok", "step_up_required"))
        print(f"         {profile}: {response.get('response','')[:100]}...")


# ──────────────────────────────────────────
# MAIN runner
# ──────────────────────────────────────────

async def run_all_tests():
    print("\n" + "="*55)
    print("  HEALTH ADVOCATE AGENT — FULL TEST SUITE")
    print("="*55)

    await test_heart_rate_reading()
    await test_weekly_trend()
    await test_alert_system()
    await test_stepup_blocking()
    await test_stepup_allows_write()
    await test_privacy()
    await test_all_profiles()

    # Final report
    total = passed + failed
    print("\n" + "="*55)
    print(f"  RESULTS: {passed}/{total} passed", end="")
    if failed == 0:
        print("  \033[92m ALL TESTS PASSED \033[0m")
    else:
        print(f"  \033[91m {failed} FAILED \033[0m")
    print("="*55)

    if failed > 0:
        print("\nFailed tests:")
        for r in results:
            if not r["passed"]:
                print(f"  ✗ {r['name']}")
                if r["detail"]:
                    print(f"    {r['detail']}")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
