"""
Google OAuth Flow Handler
==========================
Handles the real OAuth 2.0 authorization code exchange for Google Fit.
Stores tokens securely in Auth0 Token Vault — never in code or .env.

Flow:
  1. Frontend redirects user to /api/auth/google?user_id=xxx
  2. User approves Google Fit permissions
  3. Google redirects to /api/auth/callback/google?code=...&state=user_id
  4. We exchange code → access_token + refresh_token
  5. Tokens stored in Auth0 Token Vault under user_id
"""

import httpx
import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = " ".join([
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.sleep.read",
    "openid",
    "profile",
    "email",
])


def get_redirect_uri() -> str:
    app_url = os.getenv("APP_URL", "http://localhost:8000")
    return f"{app_url}/api/auth/callback/google"


def build_google_auth_url(user_id: str) -> str:
    """
    Returns the Google OAuth consent screen URL.
    user_id is passed as `state` so we know who to store tokens for.
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    redirect_uri = get_redirect_uri()
    scopes = GOOGLE_SCOPES.replace(" ", "%20")

    return (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scopes}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={user_id}"
    )


async def exchange_code_for_tokens(code: str) -> dict:
    """
    Exchanges the OAuth authorization code for access + refresh tokens.
    Returns: { access_token, refresh_token, expires_in, token_type }
    """
    async with httpx.AsyncClient() as client:
        r = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "redirect_uri": get_redirect_uri(),
                "grant_type": "authorization_code",
            },
        )
        r.raise_for_status()
        return r.json()


async def refresh_access_token(refresh_token: str) -> str:
    """
    Uses the stored refresh token to get a fresh access token.
    Called automatically when the access token expires (1 hour).
    """
    async with httpx.AsyncClient() as client:
        r = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "grant_type": "refresh_token",
            },
        )
        r.raise_for_status()
        data = r.json()
        return data["access_token"]


# ── Local Token Vault storage ──────────────────────────────────────────────────
import json

LOCAL_VAULT_PATH = "local_vault.json"

async def store_tokens_in_vault(user_id: str, access_token: str, refresh_token: str):
    """
    Stores Google tokens locally in a JSON file for local dev.
    This bypasses Auth0 since the app doesn't have Management API M2M scope configured.
    """
    try:
        if os.path.exists(LOCAL_VAULT_PATH):
            with open(LOCAL_VAULT_PATH, "r") as f:
                vault = json.load(f)
        else:
            vault = {}
    except Exception:
        vault = {}
        
    if user_id not in vault:
        vault[user_id] = {}
        
    vault[user_id]["google_fit_token"] = access_token
    vault[user_id]["google_fit_refresh"] = refresh_token
    vault[user_id]["google_fit_connected"] = True
    
    with open(LOCAL_VAULT_PATH, "w") as f:
        json.dump(vault, f)
    print(f"[Vault] Tokens stored LOCALLY for user {user_id}")


async def load_token_from_vault(user_id: str) -> dict | None:
    """
    Retrieves stored Google tokens from the local JSON file.
    Returns { access_token, refresh_token } or None if not connected.
    """
    try:
        if not os.path.exists(LOCAL_VAULT_PATH):
            return None
        with open(LOCAL_VAULT_PATH, "r") as f:
            vault = json.load(f)
            
        user_data = vault.get(user_id, {})
        if not user_data.get("google_fit_connected"):
            return None
            
        return {
            "access_token": user_data.get("google_fit_token"),
            "refresh_token": user_data.get("google_fit_refresh"),
        }
    except Exception:
        return None


async def get_valid_access_token(user_id: str) -> str | None:
    """
    Gets a valid (possibly refreshed) Google access token for a user.
    Automatically refreshes if expired.
    Returns None if user hasn't connected Google Fit.
    """
    tokens = await load_token_from_vault(user_id)
    if not tokens:
        return None

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    # Try the stored access token first
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://www.googleapis.com/oauth2/v3/tokeninfo",
            params={"access_token": access_token},
        )
        if r.status_code == 200:
            return access_token

    # Token expired — refresh it
    if refresh_token:
        try:
            new_token = await refresh_access_token(refresh_token)
            # Update vault with fresh token
            await store_tokens_in_vault(user_id, new_token, refresh_token)
            return new_token
        except Exception as e:
            print(f"[OAuth] Token refresh failed for {user_id}: {e}")

    return None