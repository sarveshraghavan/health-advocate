"""
Synthetic data & mock API patches for the demo simulator.
Provides 3 patient profiles: healthy, at_risk, recovery.

patch_all() monkey-patches the vault + tool modules so they
return realistic fake data instead of hitting real APIs.
"""

import random

# ── Patient profiles ──────────────────────────────────────

PROFILES = {
    "healthy": {
        "heart_rate": lambda: float(random.randint(62, 78)),
        "weekly_vitals": {
            "avg_hr_bpm": 70,
            "avg_steps": 9200,
            "avg_sleep_hours": 7.8,
            "daily_hr": [68, 72, 70, 74, 69, 71, 73],
            "daily_steps": [9500, 8800, 10200, 9000, 8500, 9100, 9300],
            "daily_sleep": [7.5, 8.0, 7.8, 7.6, 8.1, 7.9, 7.5],
        },
        "records": {
            "summary": "No chronic conditions. Last annual checkup: 3 months ago — all clear.",
            "medications": [],
            "allergies": ["Penicillin"],
        },
    },
    "at_risk": {
        "heart_rate": lambda: float(random.randint(95, 115)),
        "weekly_vitals": {
            "avg_hr_bpm": 102,
            "avg_steps": 3200,
            "avg_sleep_hours": 5.1,
            "daily_hr": [98, 105, 110, 99, 108, 112, 103],
            "daily_steps": [3500, 2800, 3000, 3100, 3400, 2900, 3700],
            "daily_sleep": [4.5, 5.0, 5.5, 4.8, 5.2, 5.3, 5.0],
        },
        "records": {
            "summary": "Hypertension stage 1 diagnosed 6 months ago. On daily monitoring.",
            "medications": ["Lisinopril 10mg"],
            "allergies": [],
        },
    },
    "recovery": {
        "heart_rate": lambda: float(random.randint(72, 88)),
        "weekly_vitals": {
            "avg_hr_bpm": 80,
            "avg_steps": 6800,
            "avg_sleep_hours": 6.9,
            "daily_hr": [92, 88, 85, 82, 79, 76, 74],
            "daily_steps": [5000, 5500, 6200, 6800, 7200, 7500, 8000],
            "daily_sleep": [5.5, 6.0, 6.5, 7.0, 7.2, 7.5, 7.5],
        },
        "records": {
            "summary": "Post-surgery recovery (appendectomy, 3 weeks ago). Vitals trending positive.",
            "medications": ["Ibuprofen 400mg PRN"],
            "allergies": ["Sulfa drugs"],
        },
    },
}

_current_profile = "healthy"


def set_profile(name: str):
    """Switch the active patient profile (healthy / at_risk / recovery)."""
    global _current_profile
    if name not in PROFILES:
        raise ValueError(f"Unknown profile: {name}. Choose from: {list(PROFILES.keys())}")
    _current_profile = name


def _get_profile():
    return PROFILES[_current_profile]


# ── Monkey-patch helpers ──────────────────────────────────

def patch_all():
    """
    Replace the real vault + Google Fit + FHIR calls with
    synthetic data so the demo runs without any API keys.
    """
    import tools.google_fit as gf
    import tools.fhir as fhir
    import vault

    # -- Google Fit --
    async def mock_heart_rate(user_id: str) -> float:
        return _get_profile()["heart_rate"]()

    async def mock_weekly_vitals(user_id: str) -> dict:
        return _get_profile()["weekly_vitals"]

    gf.get_heart_rate = mock_heart_rate
    gf.get_weekly_vitals = mock_weekly_vitals

    # -- FHIR --
    async def mock_get_records(user_id: str) -> dict:
        return _get_profile()["records"]

    async def mock_book_appointment(user_id, details, stepup_session_token) -> dict:
        return {"id": f"APPT-{user_id[:8]}-{random.randint(1000,9999)}", "status": "proposed"}

    async def mock_send_summary(user_id, summary, stepup_session_token) -> dict:
        return {"status": "completed", "id": f"COMM-{random.randint(1000,9999)}"}

    fhir.get_records = mock_get_records
    fhir.book_appointment = mock_book_appointment
    fhir.send_summary_to_doctor = mock_send_summary

    # -- Vault (already mocked via _is_vault_configured, but be safe) --
    async def mock_read_token(user_id, service):
        return "mock_read_token"

    async def mock_write_token(user_id, service, stepup_session_token):
        return "mock_write_token"

    vault.get_read_token = mock_read_token
    vault.get_write_token = mock_write_token

    print("[mock_apis] All APIs patched with synthetic data.")
