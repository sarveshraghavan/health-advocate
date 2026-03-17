import httpx
import time
from vault import get_read_token


async def get_heart_rate(user_id: str) -> float:
    """
    Fetches the most recent heart rate reading from Google Fit.
    """
    token = await get_read_token(user_id, "google_fit")
    if token == "mock_read_token":
        import random
        return float(random.randint(65, 85))

    now_ms = int(time.time() * 1000)
    one_hour_ago = now_ms - 3_600_000

    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "aggregateBy": [{"dataTypeName": "com.google.heart_rate.bpm"}],
                "bucketByTime": {"durationMillis": 3_600_000},
                "startTimeMillis": one_hour_ago,
                "endTimeMillis": now_ms,
            }
        )
        r.raise_for_status()

    buckets = r.json().get("bucket", [])
    if not buckets:
        return 0.0

    points = buckets[-1]["dataset"][0]["point"]
    if not points:
        return 0.0

    return points[-1]["value"][0]["fpVal"]


async def get_weekly_vitals(user_id: str) -> dict:
    """
    Fetches heart rate, steps, and sleep for the past 7 days.
    """
    token = await get_read_token(user_id, "google_fit")
    if token == "mock_read_token":
        return {
            "mock_vitals": "Daily steps avg: 8500, Sleep avg: 7.5 hours, Avg HR: 72 bpm"
        }

    now_ms = int(time.time() * 1000)
    seven_days_ago = now_ms - (7 * 24 * 3_600_000)

    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "aggregateBy": [
                    {"dataTypeName": "com.google.heart_rate.bpm"},
                    {"dataTypeName": "com.google.step_count.delta"},
                    {"dataTypeName": "com.google.sleep.segment"}
                ],
                "bucketByTime": {"durationMillis": 86_400_000},  # daily buckets
                "startTimeMillis": seven_days_ago,
                "endTimeMillis": now_ms,
            }
        )
        r.raise_for_status()

    # Return raw - this will be passed to LLM summarizer and then discarded
    return r.json()
