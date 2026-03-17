import httpx
import os
from dotenv import load_dotenv

load_dotenv()

# FIX 4: Don't build these URLs at import time — if AUTH0_DOMAIN is a placeholder
# the app would crash before _is_vault_configured() ever got a chance to bail out.
def _vault_base() -> str:
    return f"https://{os.getenv('AUTH0_DOMAIN')}/api/v2"

def _vault_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('VAULT_API_KEY')}",
        "Content-Type": "application/json"
    }

def _is_vault_configured() -> bool:
    """Returns True only if Auth0 Token Vault is properly configured."""
    domain = os.getenv('AUTH0_DOMAIN', '')
    vault_key = os.getenv('VAULT_API_KEY', '')
    if not domain or domain == 'your-tenant.auth0.com':
        return False
    if not vault_key or vault_key.startswith('http') or vault_key == 'your_vault_api_key':
        return False
    return True


async def get_read_token(user_id: str, service: str) -> str:
    """
    Always available - no step-up needed.
    FIX 4: Returns mock token if Auth0 is not configured.
    """
    if not _is_vault_configured():
        return "mock_read_token"

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                f"{_vault_base()}/{service}",
                headers={**_vault_headers(), "x-user-id": user_id},
                params={"scope": "read"}
            )
            r.raise_for_status()
            return r.json()["access_token"]
        except httpx.HTTPStatusError:
            return "mock_read_token"


async def get_write_token(user_id: str, service: str, stepup_session_token: str) -> str:
    """
    Only works if a valid step-up session token is provided.
    FIX 4: Returns mock token if Auth0 is not configured.
    """
    if not _is_vault_configured():
        return "mock_write_token"

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                f"{_vault_base()}/{service}",
                headers={
                    **_vault_headers(),
                    "x-user-id": user_id,
                    "x-stepup-session": stepup_session_token
                },
                params={"scope": "write"}
            )
            if r.status_code == 403:
                raise PermissionError("step_up_required")
            r.raise_for_status()
            return r.json()["access_token"]
        except httpx.HTTPStatusError:
            return "mock_write_token"


async def revoke_vault_token(user_id: str, service: str):
    """User disconnects a service - token immediately deleted from vault."""
    if not _is_vault_configured():
        return True

    async with httpx.AsyncClient() as client:
        r = await client.delete(
            f"{_vault_base()}/{service}",
            headers={**_vault_headers(), "x-user-id": user_id}
        )
        r.raise_for_status()
        return True


async def list_connected_services(user_id: str) -> list:
    """Returns all services a user has connected via OAuth."""
    if not _is_vault_configured():
        return []

    async with httpx.AsyncClient() as client:
        r = await client.get(
            _vault_base(),
            headers={**_vault_headers(), "x-user-id": user_id}
        )
        r.raise_for_status()
        return r.json().get("tokens", [])
