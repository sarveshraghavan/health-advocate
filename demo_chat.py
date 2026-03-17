"""
Live Demo Simulator
====================
Simulates realistic chat conversations for all 3 patient profiles.
Perfect for recording your hackathon demo video.

Run:
    cd backend
    python ../tests/demo_chat.py
"""

import asyncio
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../synthetic_data"))

from mock_apis import patch_all, set_profile
patch_all()

from agent import run_agent
from stepup import record_step_up

CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


async def simulate_chat(profile: str, user_id: str, conversations: list):
    set_profile(profile)
    print(f"\n{'='*60}")
    print(f"{BOLD}Patient Profile: {profile.upper()}{RESET}")
    print(f"User ID: {user_id}")
    print('='*60)

    for item in conversations:
        if item["type"] == "user":
            print(f"\n{CYAN}User:{RESET} {item['message']}")
            response = await run_agent(user_id, item["message"])
            status = response.get("status", "ok")

            if status == "step_up_required":
                print(f"{YELLOW}Agent:{RESET} {response.get('response','')}")
                print(f"{RED}[Step-up required]{RESET} Challenge URL: {response.get('challenge_url','mock-url')[:60]}...")

        elif item["type"] == "stepup":
            print(f"\n{YELLOW}[System: User completes biometric verification...]{RESET}")
            record_step_up(user_id)
            print(f"{GREEN}[Auth0: Step-up verified — 10-min write window granted]{RESET}")

        elif item["type"] == "agent_after_stepup":
            print(f"\n{CYAN}User:{RESET} {item['message']}")
            response = await run_agent(user_id, item["message"])
            print(f"{GREEN}Agent:{RESET} {response.get('response','')}")

        elif item["type"] == "note":
            print(f"\n{YELLOW}[Demo note: {item['text']}]{RESET}")

        if item["type"] == "user" and response.get("status") == "ok":
            print(f"{GREEN}Agent:{RESET} {response.get('response','')}")

        await asyncio.sleep(0.3)


async def run_demo():

    # ── Demo 1: Healthy user ──────────────────
    await simulate_chat("healthy", "demo-healthy-001", [
        {"type": "note",  "text": "Normal user — no alerts, positive summary expected"},
        {"type": "user",  "message": "Hey, how's my heart rate looking right now?"},
        {"type": "user",  "message": "Can you summarize how I've been doing this week?"},
        {"type": "user",  "message": "Am I getting enough sleep?"},
    ])

    # ── Demo 2: At-risk user (alert scenario) ─
    await simulate_chat("at_risk", "demo-atrisk-001", [
        {"type": "note",  "text": "High HR user — alert should fire, step-up for booking"},
        {"type": "user",  "message": "Check my heart rate please"},
        {"type": "user",  "message": "How have my vitals been this week?"},
        {"type": "user",  "message": "I'm worried — book me an appointment with Dr. Smith"},
        {"type": "stepup"},
        {"type": "agent_after_stepup", "message": "book an appointment with Dr. Smith tomorrow morning"},
        {"type": "user",  "message": "Also send a summary to my doctor"},
    ])

    # ── Demo 3: Recovery user ─────────────────
    await simulate_chat("recovery", "demo-recovery-001", [
        {"type": "note",  "text": "Improving trend — LLM should notice positive progress"},
        {"type": "user",  "message": "How have I been doing this week?"},
        {"type": "user",  "message": "Am I improving compared to earlier in the week?"},
    ])

    print(f"\n{'='*60}")
    print(f"{BOLD}{GREEN}Demo complete!{RESET}")
    print("This is exactly what to show in your hackathon video.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
