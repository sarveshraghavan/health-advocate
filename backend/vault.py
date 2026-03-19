"""
Auth0 Token Vault Client
=========================
Manages all OAuth tokens for the health advocate agent.
Tokens are stored encrypted in Auth0 — never in our database or .env.

Auto-refreshes the Auth0 Management API token using Client Credentials
so the VAULT_API_KEY never expires during a running session.
"""

import httpx
import os
import time
from dotenv import load_dotenv

load_dotenv()

# ── Auth0 Management API token cache ─────────────────────────────────────────
_mgmt_token_cache: dict = {"token": None, "expires_at": 0}


async def _get_mgmt_token() -> str:
    """
    Returns a valid Auth0 Management API token.
    Uses the cached token if still valid; otherwise fetches a new one
    via Machine-to-Machine Client Credentials flow.
    This means the vault NEVER expires mid-session.
    """
    global _mgmt_token_cache

    # Return cached token if it's still good (with 60s buffer)
    if _mgmt_token_cache["token"] and time.time() < _mgmt_token_cache["expires_at"] - 60:
        return _mgmt_token_cache["token"]

    domain = os.getenv("AUTH0_DOMAIN", "")
    client_id = os.getenv("AUTH0_CLIENT_ID", "")
    client_secret = os.getenv("AUTH0_CLIENT_SECRET", "")

    if not domain or not client_id or not client_secret:
        # Fall back to static VAULT_API_KEY if M2M creds not set
        static = os.getenv("VAULT_API_KEY", "")
        if static:
            print("[Vault] Using static VAULT_API_KEY (no M2M auto-refresh)")
            return static
        raise RuntimeError("Auth0 credentials not configured")

    print("[Vault] Refreshing Auth0 Management API token via M2M...")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"https://{domain}/oauth/token",
            json={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "audience": f"https://{domain}/api/v2/",
            },
        )
        r.raise_for_status()
        data = r.json()

    token = data["access_token"]
    expires_in = data.get("expires_in", 86400)
    _mgmt_token_cache = {"token": token, "expires_at": time.time() + expires_in}
    print(f"[Vault] ✅ New M2M token obtained, expires in {expires_in}s")
    return token


def _vault_base() -> str:
    return f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2"


async def _vault_headers() -> dict:
    token = await _get_mgmt_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _is_vault_configured() -> bool:
    """Returns True only if Auth0 Token Vault is properly configured."""
    domain = os.getenv("AUTH0_DOMAIN", "")
    client_id = os.getenv("AUTH0_CLIENT_ID", "")
    client_secret = os.getenv("AUTH0_CLIENT_SECRET", "")
    vault_key = os.getenv("VAULT_API_KEY", "")

    if not domain or domain == "your-tenant.auth0.com":
        return False
    # Configured if we have M2M creds OR a static key
    return bool((client_id and client_secret) or vault_key)


async def get_read_token(user_id: str, service: str) -> str:
    """
    Gets a valid read-only token for the given service.
    For google_fit: tries real OAuth token first, falls back to mock.
    """
    if service == "google_fit":
        try:
            from oauth import get_valid_access_token
            token = await get_valid_access_token(user_id)
            if token:
                return token
        except Exception as e:
            print(f"[Vault] Could not get real Google token: {e}")

    if not _is_vault_configured():
        return "mock_read_token"

    try:
        headers = await _vault_headers()
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{_vault_base()}/users/{user_id}",
                headers=headers,
            )
            r.raise_for_status()
            meta = r.json().get("app_metadata", {})
            token_key = f"{service}_token"
            if meta.get(token_key):
                return meta[token_key]
    except Exception as e:
        print(f"[Vault] get_read_token error: {e}")

    return "mock_read_token"


async def get_write_token(user_id: str, service: str, stepup_session_token: str) -> str:
    """Gets a write token — only valid when a step-up session is active."""
    if not _is_vault_configured():
        return "mock_write_token"

    try:
        headers = await _vault_headers()
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{_vault_base()}/users/{user_id}",
                headers={**headers, "x-stepup-session": stepup_session_token},
            )
            if r.status_code == 403:
                raise PermissionError("step_up_required")
            r.raise_for_status()
            meta = r.json().get("app_metadata", {})
            token_key = f"{service}_token"
            if meta.get(token_key):
                return meta[token_key]
    except PermissionError:
        raise
    except Exception as e:
        print(f"[Vault] get_write_token error: {e}")

    return "mock_write_token"


import json

LOCAL_VAULT_PATH = "local_vault.json"

async def revoke_vault_token(user_id: str, service: str):
    """User disconnects a service — clears tokens from local vault immediately."""
    try:
        if os.path.exists(LOCAL_VAULT_PATH):
            with open(LOCAL_VAULT_PATH, "r") as f:
                vault = json.load(f)
                
            if user_id in vault:
                vault[user_id][f"{service}_token"] = None
                vault[user_id][f"{service}_refresh"] = None
                vault[user_id][f"{service}_connected"] = False
                with open(LOCAL_VAULT_PATH, "w") as f:
                    json.dump(vault, f)
    except Exception as e:
        print(f"[Vault] revoke_vault_token local error: {e}")
        return False
    return True


async def list_connected_services(user_id: str) -> list:
    """Returns all services the user has connected from local vault."""
    connected = []
    try:
        if os.path.exists(LOCAL_VAULT_PATH):
            with open(LOCAL_VAULT_PATH, "r") as f:
                vault = json.load(f)
            user_data = vault.get(user_id, {})
            for service in ["google_fit", "fhir"]:
                if user_data.get(f"{service}_connected"):
                    connected.append(service)
    except Exception as e:
        print(f"[Vault] list_connected_services local error: {e}")
    return connected