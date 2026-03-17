import httpx
from vault import get_read_token, get_write_token
 
# Uses HAPI FHIR public sandbox - free, no account needed
FHIR_BASE = "https://hapi.fhir.org/baseR4"
 
 
async def get_records(user_id: str) -> dict:
    """
    Reads patient records from FHIR server.
    """
    token = await get_read_token(user_id, "fhir")
    if token == "mock_read_token":
        return {"mock_records": "No recent illnesses detected. Annual checkup is due next month."}
 
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{FHIR_BASE}/Patient",
            headers={"Authorization": f"Bearer {token}"},
            params={"identifier": user_id}
        )
        r.raise_for_status()
        return r.json()  # moved inside — client still open when response is read
 
 
async def book_appointment(user_id: str, details: str, stepup_session_token: str) -> dict:
    """
    Books an appointment on the FHIR server.
    """
    token = await get_write_token(user_id, "fhir", stepup_session_token)
    if token == "mock_write_token":
        return {"id": f"mock_appt_{user_id}_123", "status": "proposed"}
 
    appointment_resource = {
        "resourceType": "Appointment",
        "status": "proposed",
        "description": f"Patient requested: {details}",
        "participant": [
            {
                "actor": {"reference": f"Patient/{user_id}"},
                "status": "accepted"
            }
        ]
    }
 
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{FHIR_BASE}/Appointment",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/fhir+json"
            },
            json=appointment_resource
        )
        r.raise_for_status()
        return r.json()  # moved inside
 
 
async def send_summary_to_doctor(user_id: str, summary: str, stepup_session_token: str) -> dict:
    """
    Sends a health summary as a FHIR Communication resource.
    """
    token = await get_write_token(user_id, "fhir", stepup_session_token)
    if token == "mock_write_token":
        return {"status": "mock_completed", "id": "mock_comm_123"}
 
    communication_resource = {
        "resourceType": "Communication",
        "status": "completed",
        "subject": {"reference": f"Patient/{user_id}"},
        "payload": [
            {"contentString": summary}
        ],
        "note": [{"text": "AI-generated health trend summary. No raw data included."}]
    }
 
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{FHIR_BASE}/Communication",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/fhir+json"
            },
            json=communication_resource
        )
        r.raise_for_status()
        return r.json()  # moved inside