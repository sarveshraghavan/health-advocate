import httpx
import os
import time
import secrets
from dotenv import load_dotenv

load_dotenv()

# In-memory store: {user_id: {"timestamp": float, "session_token": str}}
# In production, use Redis with TTL
STEPUP_SESSIONS: dict = {}
STEPUP_WINDOW_SECONDS = 600  # 10 minutes


def _is_stepup_configured() -> bool:
    """FIX 4: Shared config check — mirrors vault.py's _is_vault_configured()."""
    domain = os.getenv("AUTH0_DOMAIN", "")
    vault_key = os.getenv("VAULT_API_KEY", "")
    if not domain or domain == "your-tenant.auth0.com":
        return False
    if not vault_key or vault_key.startswith("http") or vault_key == "your_vault_api_key":
        return False
    return True


def check_step_up(user_id: str) -> bool:
    """Returns True only if step-up completed within last 10 minutes."""
    session = STEPUP_SESSIONS.get(user_id)
    if not session:
        return False
    elapsed = time.time() - session["timestamp"]
    return elapsed < STEPUP_WINDOW_SECONDS


def get_stepup_session_token(user_id: str) -> str | None:
    """Returns the session token if step-up is still valid."""
    if not check_step_up(user_id):
        return None
    return STEPUP_SESSIONS[user_id]["session_token"]


def record_step_up(user_id: str) -> str:
    """Called after Auth0 confirms MFA/biometric. Returns session token."""
    session_token = secrets.token_urlsafe(32)
    STEPUP_SESSIONS[user_id] = {
        "timestamp": time.time(),
        "session_token": session_token
    }
    return session_token


def get_remaining_window(user_id: str) -> int:
    """Returns seconds remaining in the step-up window (0 if expired)."""
    session = STEPUP_SESSIONS.get(user_id)
    if not session:
        return 0
    elapsed = time.time() - session["timestamp"]
    remaining = STEPUP_WINDOW_SECONDS - elapsed
    return max(0, int(remaining))


async def request_step_up_url(user_id: str, action: str) -> str:
    """
    Generates the Auth0 MFA/biometric challenge URL.
    FIX 4: If Auth0 is not configured, returns a local mock callback URL
    so the demo flow completes without needing a real Auth0 tenant.
    """
    if not _is_stepup_configured():
        app_url = os.getenv("APP_URL", "http://localhost:8000")
        return f"{app_url}/stepup/callback?code=mock_code_123&state={user_id}:{action}"

    params = {
        "client_id": os.getenv("AUTH0_CLIENT_ID"),
        "redirect_uri": f"{os.getenv('APP_URL')}/stepup/callback",
        "response_type": "code",
        "scope": "openid",
        "acr_values": "http://schemas.openid.net/pape/policies/2007/06/multi-factor",
        "state": f"{user_id}:{action}",
        "prompt": "login"
    }
    base = f"https://{os.getenv('AUTH0_DOMAIN')}/authorize"
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base}?{query}"


async def stepup_callback_handler(code: str, state: str) -> dict:
    """
    Called by Auth0 after user completes biometric/MFA.
    FIX 4: mock_code_123 is accepted as a valid bypass so the demo
    appointment/share flows work without a real Auth0 tenant.
    """
    user_id, action = state.split(":", 1)

    if code == "mock_code_123":
        session_token = record_step_up(user_id)
        return {
            "status": "verified",
            "user_id": user_id,
            "action": action,
            "session_token": session_token,
            "window_seconds": STEPUP_WINDOW_SECONDS
        }

    # Exchange code for tokens (real Auth0 flow)
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://{os.getenv('AUTH0_DOMAIN')}/oauth/token",
            json={
                "grant_type": "authorization_code",
                "client_id": os.getenv("AUTH0_CLIENT_ID"),
                "client_secret": os.getenv("AUTH0_CLIENT_SECRET"),
                "code": code,
                "redirect_uri": f"{os.getenv('APP_URL')}/stepup/callback"
            }
        )
        r.raise_for_status()

    # In production: verify the id_token contains an MFA amr claim
    session_token = record_step_up(user_id)

    return {
        "status": "verified",
        "user_id": user_id,
        "action": action,
        "session_token": session_token,
        "window_seconds": STEPUP_WINDOW_SECONDS
    }
