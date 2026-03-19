"""
Google Fit API — Real Data
===========================
Fetches live heart rate, steps, and sleep from the Google Fit REST API.
Uses the real OAuth access token stored in Auth0 Token Vault.
Falls back to mock data gracefully if the user hasn't connected yet.
"""

import httpx
import time


async def _get_live_token(user_id: str) -> str | None:
    """
    Gets a real OAuth token from the vault.
    Returns None if user hasn't connected Google Fit.
    """
    try:
        from oauth import get_valid_access_token
        return await get_valid_access_token(user_id)
    except Exception as e:
        print(f"[GoogleFit] Could not get live token: {e}")
        return None


async def get_heart_rate(user_id: str) -> float:
    """
    Fetches the most recent heart rate reading from Google Fit.
    Uses real OAuth token if available, else returns mock value.
    """
    token = await _get_live_token(user_id)

    if not token:
        # Not connected yet — return mock value so agent still works
        import random
        print(f"[GoogleFit] No real token for {user_id}, using mock HR")
        return float(random.randint(65, 85))

    now_ms = int(time.time() * 1000)
    # Changed from 1 hour to 3 days for the demo, so it's more forgiving 
    # if the user's device hasn't synced in the last 60 minutes.
    three_days_ago = now_ms - (3 * 24 * 3_600_000)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "aggregateBy": [{"dataTypeName": "com.google.heart_rate.bpm"}],
                    "bucketByTime": {"durationMillis": 3_600_000},
                    "startTimeMillis": three_days_ago,
                    "endTimeMillis": now_ms,
                },
            )
            r.raise_for_status()

        buckets = r.json().get("bucket", [])
        if not buckets:
            print(f"[GoogleFit] No HR buckets returned for {user_id}")
            return 0.0

        # Walk buckets from most recent backwards to find a reading
        for bucket in reversed(buckets):
            datasets = bucket.get("dataset", [])
            for dataset in datasets:
                points = dataset.get("point", [])
                if points:
                    bpm = points[-1]["value"][0]["fpVal"]
                    print(f"[GoogleFit] Live HR for {user_id}: {bpm} BPM")
                    return float(bpm)

        print(f"[GoogleFit] No HR data points found for {user_id}")
        return 0.0

    except httpx.HTTPStatusError as e:
        print(f"[GoogleFit] HR fetch failed ({e.response.status_code}): {e.response.text[:200]}")
        return 0.0
    except Exception as e:
        print(f"[GoogleFit] HR fetch error: {e}")
        return 0.0


async def get_weekly_vitals(user_id: str) -> dict:
    """
    Fetches heart rate, steps, and sleep for the past 7 days from Google Fit.
    Returns structured dict the LLM can summarise.
    Falls back to mock vitals if user hasn't connected.
    """
    token = await _get_live_token(user_id)

    if not token:
        print(f"[GoogleFit] No real token for {user_id}, using mock weekly vitals")
        return {
            "mock_vitals": True,
            "note": "Google Fit not connected. Showing demo data.",
            "avg_steps": 8500,
            "avg_sleep_hours": 7.5,
            "avg_hr_bpm": 72,
        }

    now_ms = int(time.time() * 1000)
    seven_days_ago = now_ms - (7 * 24 * 3_600_000)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "aggregateBy": [
                        {"dataTypeName": "com.google.heart_rate.bpm"},
                        {"dataTypeName": "com.google.step_count.delta"},
                        {"dataTypeName": "com.google.sleep.segment"},
                    ],
                    "bucketByTime": {"durationMillis": 86_400_000},  # daily buckets
                    "startTimeMillis": seven_days_ago,
                    "endTimeMillis": now_ms,
                },
            )
            r.raise_for_status()

        raw = r.json()
        return _parse_weekly_vitals(raw)

    except httpx.HTTPStatusError as e:
        print(f"[GoogleFit] Weekly vitals fetch failed ({e.response.status_code})")
        return {"error": f"Google Fit returned {e.response.status_code}"}
    except Exception as e:
        print(f"[GoogleFit] Weekly vitals error: {e}")
        return {"error": str(e)}


def _parse_weekly_vitals(raw: dict) -> dict:
    """
    Parses the raw Google Fit aggregate response into a clean summary dict.
    The LLM sees this — we keep it structured but human-readable.
    Raw numbers are present here but the agent prompt instructs the LLM
    NOT to repeat exact values in its response.
    """
    daily_hr = []
    daily_steps = []
    daily_sleep_minutes = []

    for bucket in raw.get("bucket", []):
        datasets = bucket.get("dataset", [])

        hr_val = None
        steps_val = 0
        sleep_val = 0

        for dataset in datasets:
            data_type = dataset.get("dataSourceId", "")
            points = dataset.get("point", [])

            if "heart_rate" in data_type and points:
                # Average HR across the day's points
                vals = [p["value"][0]["fpVal"] for p in points if p.get("value")]
                if vals:
                    hr_val = round(sum(vals) / len(vals), 1)

            elif "step_count" in data_type and points:
                steps_val = sum(
                    p["value"][0].get("intVal", 0)
                    for p in points if p.get("value")
                )

            elif "sleep" in data_type and points:
                # Sleep segment durations in milliseconds
                for p in points:
                    start = int(p.get("startTimeNanos", 0)) // 1_000_000
                    end = int(p.get("endTimeNanos", 0)) // 1_000_000
                    sleep_val += (end - start)

        if hr_val is not None:
            daily_hr.append(hr_val)
        if steps_val > 0:
            daily_steps.append(steps_val)
        if sleep_val > 0:
            daily_sleep_minutes.append(round(sleep_val / 60_000, 1))  # ms → minutes

    # Build summary
    result = {"source": "google_fit_live", "days_with_data": len(daily_hr)}

    if daily_hr:
        result["avg_hr_bpm"] = round(sum(daily_hr) / len(daily_hr), 1)
        result["min_hr_bpm"] = min(daily_hr)
        result["max_hr_bpm"] = max(daily_hr)
        result["daily_hr_bpm"] = daily_hr

    if daily_steps:
        result["avg_steps_per_day"] = round(sum(daily_steps) / len(daily_steps))
        result["total_steps"] = sum(daily_steps)
        result["daily_steps"] = daily_steps

    if daily_sleep_minutes:
        avg_sleep_hours = round(sum(daily_sleep_minutes) / len(daily_sleep_minutes) / 60, 1)
        result["avg_sleep_hours"] = avg_sleep_hours
        result["daily_sleep_minutes"] = daily_sleep_minutes

    if not daily_hr and not daily_steps:
        result["note"] = "No data recorded in Google Fit for this period. Make sure your device is syncing."

    return result
    