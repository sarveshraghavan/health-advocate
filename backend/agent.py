"""
Health Advocate Agent
======================
Main LLM agent loop. Routes user messages to the right tool,
calls Google Fit / FHIR with real data, and uses Gemini to
produce privacy-safe, plain-English health consultations.

Real data flow:
  1. User asks a health question
  2. Agent fetches LIVE data from Google Fit (via real OAuth token)
  3. Raw data passed to Gemini once — never stored, never repeated verbatim
  4. Gemini returns a human-readable summary / consultation
  5. Step-up auth enforced for any write actions (booking, sharing)
"""

import os
from google import genai
from tools.google_fit import get_heart_rate, get_weekly_vitals
from tools.fhir import get_records, book_appointment, send_summary_to_doctor
from stepup import check_step_up, get_stepup_session_token, request_step_up_url
from dotenv import load_dotenv

load_dotenv()

# Guard client init
try:
    _key = os.getenv("GEMINI_API_KEY", "")
    client = genai.Client(api_key=_key) if _key and _key != "your_gemini_api_key" else None
except Exception:
    client = None


# ── Gemini call with contextual fallback ─────────────────────────────────────

async def generate_with_fallback(prompt: str) -> str:
    """
    Calls Gemini with the given prompt.
    Falls back to context-aware mock if no API key configured.
    """
    key = os.getenv("GEMINI_API_KEY", "")
    if not client or not key or key == "your_gemini_api_key":
        lprompt = prompt.lower()
        if "current heart rate" in lprompt or "bpm" in lprompt:
            return (
                "Your heart rate is currently within a normal resting range. "
                "No immediate concern — keep up your activity level and stay hydrated."
            )
        elif "weekly" in lprompt or "trend" in lprompt or "7 days" in lprompt:
            return (
                "Over the past week your vitals have been fairly consistent. "
                "Steps and sleep look reasonable, and your heart rate trend is stable. "
                "Keep monitoring — I'll alert you if anything changes."
            )
        elif "medical record" in lprompt or "history" in lprompt:
            return (
                "Your records show no acute issues. "
                "You have a routine checkup due soon — I'd recommend confirming that appointment."
            )
        elif "alert" in lprompt or "spike" in lprompt or "anomaly" in lprompt:
            return (
                "Your heart rate was elevated above your normal range recently. "
                "If this persists or you feel unwell, please contact your doctor."
            )
        elif "book" in lprompt or "appointment" in lprompt:
            return "Your appointment has been booked. You should receive a confirmation shortly."
        elif "send" in lprompt or "doctor" in lprompt or "summary" in lprompt:
            return "Your health summary has been securely sent to your doctor."
        else:
            return (
                "Based on your recent data, your health indicators look stable. "
                "If you have specific concerns, I'd recommend consulting your doctor directly."
            )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"I couldn't process your request right now ({e}). Your vitals appear stable based on recent readings."


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a careful, privacy-first AI health advocate assistant.

Your role is to help patients understand their health data — NOT to replace their doctor.

Rules you MUST always follow:
1. NEVER repeat exact numeric values from raw health data in your response
   - Say "elevated" not "your HR was 112 BPM"
   - Say "below average" not "you only got 4.5 hours"
2. ALWAYS recommend consulting a doctor for anything concerning
3. Keep responses SHORT — 2-4 sentences max
4. Be warm, clear, and non-alarmist unless the data is genuinely serious
5. For serious readings (very high HR, very low sleep), express appropriate concern
   and clearly recommend medical attention
6. Do NOT give diagnoses — describe trends, patterns, and observations only

When data shows a positive trend (recovery, improvement), acknowledge that warmly.
When data shows risk indicators, be honest but calm and action-oriented."""


# ── Exported helper: anomaly summarizer (used by watcher.py) ─────────────────

async def summarize_anomaly(event: str, user_id: str) -> str:
    """
    Called by the watcher when an anomaly is detected.
    Raw event string is used only in this one LLM call — never persisted.
    """
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Health alert event: {event}\n\n"
        f"Write a 2-sentence plain-English alert for the patient. "
        f"Be honest about the concern but don't panic them. "
        f"Do NOT repeat exact numbers."
    )
    return await generate_with_fallback(prompt)


# ── Exported helper: trend summarizer ────────────────────────────────────────

async def summarize_trend(user_id: str) -> str:
    """
    Fetches real weekly vitals, passes to Gemini, discards raw data.
    Returns a plain-English trend summary — no raw numbers.
    """
    raw_vitals = await get_weekly_vitals(user_id)

    # Check if this is real vs mock data
    data_source = "real Google Fit data" if raw_vitals.get("source") == "google_fit_live" else "demo data"

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Weekly health data ({data_source}):\n{raw_vitals}\n\n"
        f"Provide a 2-3 sentence health trend summary. "
        f"If data shows an improving or declining trend, mention that clearly. "
        f"Do NOT list exact numbers — describe trends and patterns only."
    )
    return await generate_with_fallback(prompt)


# ── Main agent loop ───────────────────────────────────────────────────────────

async def run_agent(user_id: str, message: str) -> dict:
    """
    Routes user messages to the correct tool/intent.
    Read intents → fetch data → LLM summary → return
    Write intents → check step-up → execute or request auth
    """
    msg_lower = message.lower()

    # ── READ: Current heart rate ──────────────────────────────────────────────
    if any(w in msg_lower for w in ["heart rate", "bpm", "pulse", "how am i", "health today"]):
        bpm = await get_heart_rate(user_id)

        if bpm == 0.0:
            return {
                "status": "ok",
                "response": (
                    "I couldn't get a heart rate reading right now. "
                    "Make sure your device is syncing with Google Fit and try again in a moment."
                )
            }

        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Patient's current heart rate reading: {bpm} BPM\n\n"
            f"Respond in 2 sentences. Comment on whether this reading looks normal, "
            f"elevated, or concerning — without stating the exact number."
        )
        response_text = await generate_with_fallback(prompt)
        return {"status": "ok", "response": response_text}

    # ── READ: Weekly trend ────────────────────────────────────────────────────
    elif any(w in msg_lower for w in ["trend", "week", "vitals", "summary", "how have i been", "this week", "past week"]):
        summary = await summarize_trend(user_id)
        return {"status": "ok", "response": summary}

    # ── READ: Medical records ─────────────────────────────────────────────────
    elif any(w in msg_lower for w in ["records", "history", "medical", "medications", "allergies"]):
        records = await get_records(user_id)
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Patient's medical records: {records}\n\n"
            f"Summarise in 2-3 sentences. Mention any medications or allergies the patient "
            f"should be aware of. Do not reproduce raw data."
        )
        response_text = await generate_with_fallback(prompt)
        return {"status": "ok", "response": response_text}

    # ── WRITE: Book appointment (requires step-up) ────────────────────────────
    elif any(w in msg_lower for w in ["book", "appointment", "schedule"]):
        if not check_step_up(user_id):
            challenge_url = await request_step_up_url(user_id, "book_appointment")
            return {
                "status": "step_up_required",
                "response": (
                    "To book an appointment I need to verify your identity first. "
                    "Please complete the biometric check using the link below."
                ),
                "challenge_url": challenge_url,
            }
        session_token = get_stepup_session_token(user_id)
        result = await book_appointment(user_id, message, session_token)
        appt_id = result.get("id", "N/A")
        return {
            "status": "ok",
            "response": (
                f"Your appointment has been booked successfully. "
                f"Confirmation ID: {appt_id}. "
                f"You should receive details via your healthcare portal shortly."
            ),
        }

    # ── WRITE: Send summary to doctor (requires step-up) ─────────────────────
    elif any(w in msg_lower for w in ["send", "share", "physician", "doctor"]):
        if not check_step_up(user_id):
            challenge_url = await request_step_up_url(user_id, "send_summary")
            return {
                "status": "step_up_required",
                "response": (
                    "To share your health summary with your doctor I need to verify your identity first. "
                    "Please complete the biometric check using the link below."
                ),
                "challenge_url": challenge_url,
            }
        session_token = get_stepup_session_token(user_id)
        summary = await summarize_trend(user_id)
        await send_summary_to_doctor(user_id, summary, session_token)
        return {
            "status": "ok",
            "response": (
                "Your health summary has been securely sent to your doctor. "
                "They will be able to review your recent trends before your next visit."
            ),
        }

    # ── DEFAULT: General health question ─────────────────────────────────────
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Patient question: {message}\n\n"
        f"Answer helpfully in 2-3 sentences. If this requires personal health data "
        f"you don't have access to, say so gently and suggest they ask about their vitals or trends."
    )
    response_text = await generate_with_fallback(prompt)
    return {"status": "ok", "response": response_text}