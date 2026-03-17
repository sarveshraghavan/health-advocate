import os
from google import genai
from tools.google_fit import get_heart_rate, get_weekly_vitals
from tools.fhir import get_records, book_appointment, send_summary_to_doctor
from stepup import check_step_up, get_stepup_session_token, request_step_up_url
from dotenv import load_dotenv

load_dotenv()

# FIX 2 + 3: Guard client init — don't crash on missing/invalid key.
# Uses new genai.Client() syntax from `google-genai` package (not the old google-generativeai).
try:
    _key = os.getenv("GEMINI_API_KEY", "")
    client = genai.Client(api_key=_key) if _key and _key != "your_gemini_api_key" else None
except Exception:
    client = None


async def generate_with_fallback(prompt: str) -> str:
    """
    FIX 2: If key is missing/placeholder, return a contextual mock response
    instead of crashing with a 400/404.
    FIX 3: Uses the new `client.models.generate_content` API with gemini-2.5-flash.
    """
    key = os.getenv("GEMINI_API_KEY", "")
    if not client or not key or key == "your_gemini_api_key":
        lprompt = prompt.lower()
        if "current reading:" in lprompt:
            return "[MOCK AI]: Your heart rate is currently looking normal! It's within a healthy range right now."
        elif "weekly vitals data:" in lprompt:
            return "[MOCK AI]: Over the past week, your steps, sleep, and heart rate have been very steady. Keep up the good work!"
        elif "medical records summary:" in lprompt:
            return "[MOCK AI]: Your records show no major issues. You have an upcoming routine checkup soon."
        elif "health alert event:" in lprompt:
            return "[MOCK AI]: You had a slight heart rate spike, but it seems to have settled. Please monitor it."
        else:
            return "[MOCK AI]: Since I'm running in demo mode without an API key, I can't answer complex questions. But your general health metrics look stable!"

    try:
        # FIX 3: New SDK syntax — genai.Client().models.generate_content()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"[MOCK AI]: API request failed ({e}). Mock response: Your vitals look normal for this week."


SYSTEM_PROMPT = """You are a careful, privacy-first health advocate assistant.

Rules you MUST follow:
1. NEVER repeat exact numeric values from raw health data in your response
2. NEVER store or reference previous raw data - only refer to summaries
3. NEVER give medical diagnoses - always recommend consulting a doctor
4. Keep responses SHORT and plain-English (2-3 sentences max per topic)
5. If the user asks to take an action (book, send), say what you'll do and check auth

You help users understand health trends, not replace their doctor."""


async def summarize_anomaly(event: str, user_id: str) -> str:
    """
    Called by the watcher when an anomaly is detected.
    Raw event data used only in this LLM call - never persisted.
    """
    prompt = f"{SYSTEM_PROMPT}\n\nHealth alert event: {event}\n\nWrite a 2-sentence plain-English alert for the patient. Do not repeat exact numbers."
    response_text = await generate_with_fallback(prompt)
    return response_text


async def summarize_trend(user_id: str) -> str:
    """
    Fetches raw vitals, summarizes via LLM, discards raw data.
    """
    raw_vitals = await get_weekly_vitals(user_id)
    prompt = f"{SYSTEM_PROMPT}\n\nWeekly vitals data: {raw_vitals}\n\nProvide a brief 2-3 sentence health trend summary. Do not list exact numbers."
    response_text = await generate_with_fallback(prompt)
    return response_text


async def run_agent(user_id: str, message: str) -> dict:
    """
    Main agent loop. Routes user messages to the right tool.
    Returns response dict with status and message.
    """
    msg_lower = message.lower()

    # READ intents - no step-up needed
    if any(w in msg_lower for w in ["heart rate", "bpm", "how am i", "health today"]):
        bpm = await get_heart_rate(user_id)
        prompt = f"{SYSTEM_PROMPT}\n\nCurrent reading: {bpm} BPM\n\nRespond in 1-2 sentences without stating the exact number."
        response_text = await generate_with_fallback(prompt)
        return {"status": "ok", "response": response_text}

    elif any(w in msg_lower for w in ["trend", "week", "vitals", "summary", "how have i been"]):
        summary = await summarize_trend(user_id)
        return {"status": "ok", "response": summary}

    elif any(w in msg_lower for w in ["records", "history", "medical"]):
        records = await get_records(user_id)
        prompt = f"{SYSTEM_PROMPT}\n\nMedical records summary: {records}\n\nSummarise in 2-3 sentences."
        response_text = await generate_with_fallback(prompt)
        return {"status": "ok", "response": response_text}

    # WRITE intents - step-up required
    elif any(w in msg_lower for w in ["book", "appointment", "schedule", "doctor"]):
        if not check_step_up(user_id):
            challenge_url = await request_step_up_url(user_id, "book_appointment")
            return {
                "status": "step_up_required",
                "response": "To book an appointment, I need to verify your identity first. Please complete the biometric check.",
                "challenge_url": challenge_url
            }
        session_token = get_stepup_session_token(user_id)
        result = await book_appointment(user_id, message, session_token)
        return {"status": "ok", "response": f"Appointment booked successfully. Confirmation: {result.get('id', 'N/A')}"}

    elif any(w in msg_lower for w in ["send", "share", "physician"]):
        if not check_step_up(user_id):
            challenge_url = await request_step_up_url(user_id, "send_summary")
            return {
                "status": "step_up_required",
                "response": "To share your health summary with your doctor, I need to verify your identity first.",
                "challenge_url": challenge_url
            }
        session_token = get_stepup_session_token(user_id)
        summary = await summarize_trend(user_id)
        await send_summary_to_doctor(user_id, summary, session_token)
        return {"status": "ok", "response": "Your health summary has been securely sent to your doctor."}

    # Default: general health question
    prompt = f"{SYSTEM_PROMPT}\n\nUser question: {message}\n\nAnswer helpfully in 2-3 sentences."
    response_text = await generate_with_fallback(prompt)
    return {"status": "ok", "response": response_text}
