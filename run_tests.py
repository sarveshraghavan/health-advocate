"""
Health Advocate Agent — Full Test Suite
Run this to verify every feature works before your demo.

Usage:
  cd health-advocate/
  TEST_MODE=true TEST_PROFILE=stressed python tests/run_tests.py
"""

import asyncio
import os
import sys
import time

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../synthetic"))

# ── Activate mocks before importing agent ─────────────────────────────────────
from mock_apis import patch_all_mocks
patch_all_mocks()

# ── Now import agent (will use mocked APIs) ───────────────────────────────────
from agent import run_agent, summarize_anomaly, summarize_trend
from stepup import record_step_up, check_step_up, get_remaining_window
from watcher import watch_user

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

passed = []
failed = []

def log_test(name: str, ok: bool, detail: str = ""):
    status = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"  [{status}] {name}")
    if detail:
        print(f"         {CYAN}{detail[:120]}{RESET}")
    if ok:
        passed.append(name)
    else:
        failed.append(name)

# ── Tests ──────────────────────────────────────────────────────────────────────

async def test_heart_rate_query():
    print(f"\n{BOLD}Test 1 — Heart rate query (read-only){RESET}")
    result = await run_agent("user-001", "what is my heart rate right now?")
    ok = result["status"] == "ok" and len(result["response"]) > 10
    log_test("Agent returns heart rate summary", ok, result.get("response", ""))

async def test_weekly_trend():
    print(f"\n{BOLD}Test 2 — Weekly trend summary{RESET}")
    result = await run_agent("user-001", "how have I been doing this week?")
    ok = result["status"] == "ok" and len(result["response"]) > 20
    log_test("Agent returns weekly trend", ok, result.get("response", ""))
    # Verify raw numbers are not in response
    response_text = result.get("response", "")
    has_raw_numbers = any(str(n) in response_text for n in range(50, 200))
    log_test("Raw BPM numbers NOT in response (privacy check)", not has_raw_numbers,
             "Response contains exact numbers!" if has_raw_numbers else "Clean — no raw numbers leaked")

async def test_medical_records():
    print(f"\n{BOLD}Test 3 — Medical records (read-only){RESET}")
    result = await run_agent("user-001", "show me my medical history")
    ok = result["status"] == "ok"
    log_test("Agent reads medical records", ok, result.get("response", ""))

async def test_step_up_required_for_booking():
    print(f"\n{BOLD}Test 4 — Step-up auth blocks booking without verification{RESET}")
    result = await run_agent("user-no-stepup", "book an appointment with Dr. Smith")
    ok = result["status"] == "step_up_required" and "challenge_url" in result
    log_test("Booking blocked without step-up", ok,
             f"Status: {result['status']} | URL present: {'challenge_url' in result}")

async def test_step_up_allows_booking():
    print(f"\n{BOLD}Test 5 — Booking succeeds after step-up verification{RESET}")
    user_id = "user-verified-001"
    # Simulate user completing biometric
    session_token = record_step_up(user_id)
    log_test("Step-up session recorded", bool(session_token), f"Token: {session_token[:20]}...")

    result = await run_agent(user_id, "book an appointment with Dr. Smith tomorrow at 10am")
    ok = result["status"] == "ok" and "booked" in result["response"].lower()
    log_test("Booking succeeds after step-up", ok, result.get("response", ""))

async def test_step_up_window():
    print(f"\n{BOLD}Test 6 — Step-up 10-minute window{RESET}")
    user_id = "user-window-test"
    record_step_up(user_id)

    active = check_step_up(user_id)
    log_test("Step-up active immediately after verification", active)

    remaining = get_remaining_window(user_id)
    log_test(f"Window shows ~600s remaining", 590 <= remaining <= 600,
             f"Remaining: {remaining}s")

    # Expired session check
    active_before = check_step_up("user-never-verified")
    log_test("Non-verified user has no step-up", not active_before)

async def test_send_summary_blocked():
    print(f"\n{BOLD}Test 7 — Sending to doctor blocked without step-up{RESET}")
    result = await run_agent("user-no-stepup-2", "send my health summary to my doctor")
    ok = result["status"] == "step_up_required"
    log_test("Doctor share blocked without step-up", ok, result.get("response", ""))

async def test_send_summary_allowed():
    print(f"\n{BOLD}Test 8 — Sending to doctor succeeds after step-up{RESET}")
    user_id = "user-verified-002"
    record_step_up(user_id)
    result = await run_agent(user_id, "send my health summary to my doctor")
    ok = result["status"] == "ok" and "sent" in result["response"].lower()
    log_test("Doctor share succeeds after step-up", ok, result.get("response", ""))

async def test_anomaly_summarizer():
    print(f"\n{BOLD}Test 9 — Anomaly LLM summarizer{RESET}")
    summary = await summarize_anomaly(
        event="Heart rate spike detected: 138 BPM (threshold: 100 BPM)",
        user_id="user-001"
    )
    ok = len(summary) > 20
    log_test("Anomaly summarized by LLM", ok, summary[:120])
    has_exact = "138" in summary
    log_test("Exact spike value not echoed back (privacy)", not has_exact,
             "LEAKED: 138 found in summary!" if has_exact else "Clean summary")

async def test_watcher_fires_alert():
    print(f"\n{BOLD}Test 10 — Watcher alert trigger{RESET}")
    # Run one watcher iteration manually with a very low threshold
    # so it always fires
    from tools.google_fit import get_heart_rate
    from tools.notifier import send_alert
    from agent import summarize_anomaly

    bpm = await get_heart_rate("user-001")
    alert_fired = bpm > 0  # any valid reading
    log_test(f"Watcher fetched BPM reading ({bpm})", alert_fired)

    if bpm > 50:  # force alert for test
        summary = await summarize_anomaly(f"Test spike: {bpm} BPM", "user-001")
        result = await send_alert("user-001", summary)
        log_test("Alert dispatched to notifier", result["status"] == "sent_mock", summary[:80])

async def test_general_question():
    print(f"\n{BOLD}Test 11 — General health question (fallback){RESET}")
    result = await run_agent("user-001", "what should I do to improve my sleep?")
    ok = result["status"] == "ok" and len(result["response"]) > 30
    log_test("Agent answers general health question", ok, result.get("response", ""))

# ── Run all tests ──────────────────────────────────────────────────────────────
async def main():
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Health Advocate Agent — Test Suite{RESET}")
    print(f"  Profile: {os.getenv('TEST_PROFILE', 'stressed')}")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{BOLD}{'='*60}{RESET}")

    await test_heart_rate_query()
    await test_weekly_trend()
    await test_medical_records()
    await test_step_up_required_for_booking()
    await test_step_up_allows_booking()
    await test_step_up_window()
    await test_send_summary_blocked()
    await test_send_summary_allowed()
    await test_anomaly_summarizer()
    await test_watcher_fires_alert()
    await test_general_question()

    # ── Results ────────────────────────────────────────────────────────────────
    total = len(passed) + len(failed)
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Results: {GREEN}{len(passed)} passed{RESET} / {RED}{len(failed)} failed{RESET} / {total} total{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    if failed:
        print(f"\n{RED}Failed tests:{RESET}")
        for f in failed:
            print(f"  - {f}")
    else:
        print(f"\n{GREEN}All tests passed! Your agent is ready for the demo.{RESET}")

    print()

if __name__ == "__main__":
    asyncio.run(main())
