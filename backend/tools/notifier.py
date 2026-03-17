import httpx
import os
from dotenv import load_dotenv

load_dotenv()


async def send_alert(user_id: str, message: str):
    """
    Sends an SMS alert via Twilio free trial.
    In demo mode, just prints to console if Twilio not configured.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    to_number = os.getenv("TWILIO_TO_NUMBER")  # demo: one recipient

    if not all([account_sid, auth_token, from_number, to_number]):
        # Demo mode - log alert instead of sending SMS
        print(f"[ALERT] User {user_id}: {message}")
        return {"status": "logged", "message": message}

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
            auth=(account_sid, auth_token),
            data={
                "From": from_number,
                "To": to_number,
                "Body": f"Health Alert: {message}"
            }
        )
        r.raise_for_status()

    return r.json()
