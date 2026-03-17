import asyncio
from tools.google_fit import get_heart_rate
from tools.notifier import send_alert
from agent import summarize_anomaly

# Active watcher flags: {user_id: bool}
_watchers: dict = {}


async def watch_user(user_id: str, threshold_bpm: int = 100):
    """
    Background loop: polls heart rate every 5 minutes.
    Fires an LLM-summarized alert if threshold exceeded.
    Raw data is NEVER saved - only the summary goes to the notifier.
    """
    _watchers[user_id] = True
    print(f"[Watcher] Started for user {user_id}, threshold={threshold_bpm} BPM")

    while _watchers.get(user_id, False):
        try:
            bpm = await get_heart_rate(user_id)

            if bpm > 0 and bpm > threshold_bpm:
                # Raw BPM used only in this call - never written to DB
                summary = await summarize_anomaly(
                    event=f"Heart rate spike detected: {bpm} BPM (threshold: {threshold_bpm} BPM)",
                    user_id=user_id
                )
                await send_alert(user_id, summary)
                print(f"[Watcher] Alert sent for user {user_id}: {bpm} BPM")
            else:
                print(f"[Watcher] User {user_id}: {bpm} BPM - normal")

        except Exception as e:
            print(f"[Watcher] Error for user {user_id}: {e}")

        # Poll every 5 minutes
        await asyncio.sleep(300)

    print(f"[Watcher] Stopped for user {user_id}")


def stop_watching(user_id: str):
    """Gracefully stops the watcher loop for a user."""
    _watchers[user_id] = False
