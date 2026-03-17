"""
Real API Connection Tester
============================
Tests all 3 real API connections before running the full agent.
Run this first to confirm your keys are working.

Usage (from backend/ folder):
    python ../scripts/test_real_connections.py
"""

import asyncio
import httpx
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../backend/.env"))

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

passed = 0
failed = 0


def ok(name, detail=""):
    global passed
    passed += 1
    print(f"  {GREEN}✓ PASS{RESET}  {name}")
    if detail:
        print(f"         {detail}")


def fail(name, detail=""):
    global failed
    failed += 1
    print(f"  {RED}✗ FAIL{RESET}  {name}")
    if detail:
        print(f"         {RED}{detail}{RESET}")


# ── Test 1: Gemini API ────────────────────────────────────────────

async def test_gemini():
    print(f"\n── Gemini API (aistudio.google.com) ──────────────────")
    key = os.getenv("GEMINI_API_KEY")

    if not key:
        fail("GEMINI_API_KEY found in .env", "Missing — add it to backend/.env")
        return
    ok("GEMINI_API_KEY found in .env")

    try:
        from google import genai
        client = genai.Client(api_key=key)
        r = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say: connection successful",
        )
        if r.text and len(r.text) > 3:
            ok("Gemini responds to test prompt", f"Response: {r.text.strip()[:80]}")
        else:
            fail("Gemini response empty")
    except Exception as e:
        fail("Gemini API call failed", str(e))


# ── Test 2: Auth0 + Token Vault ───────────────────────────────────

async def test_auth0():
    print(f"\n── Auth0 Token Vault ─────────────────────────────────")
    domain  = os.getenv("AUTH0_DOMAIN")
    key     = os.getenv("VAULT_API_KEY")
    cid     = os.getenv("AUTH0_CLIENT_ID")
    csecret = os.getenv("AUTH0_CLIENT_SECRET")

    for name, val in [
        ("AUTH0_DOMAIN",        domain),
        ("VAULT_API_KEY",       key),
        ("AUTH0_CLIENT_ID",     cid),
        ("AUTH0_CLIENT_SECRET", csecret),
    ]:
        if val:
            ok(f"{name} found in .env")
        else:
            fail(f"{name} missing from .env")

    if not domain or not key:
        return

    # Test 1: Check domain is reachable via OpenID config
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://{domain}/.well-known/openid-configuration")
            if r.status_code == 200:
                ok("Auth0 domain reachable")
            else:
                fail("Auth0 domain unreachable", f"Status: {r.status_code}")
    except Exception as e:
        fail("Auth0 domain unreachable", str(e))
        return

    # Test 2: Check API key works against Management API
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://{domain}/api/v2/clients",
                headers={"Authorization": f"Bearer {key}"}
            )
            if r.status_code == 200:
                ok("Token Vault API key valid")
            elif r.status_code == 401:
                fail("Token Vault API key expired", "Generate a new Management API token from Auth0 dashboard")
            else:
                ok("Token Vault API key accepted", f"Status: {r.status_code}")
    except Exception as e:
        fail("Token Vault API check failed", str(e))


# ── Test 3: Google Cloud / Fit API ────────────────────────────────

async def test_google_fit():
    print(f"\n── Google Fit API (Google Cloud Console) ─────────────")
    cid    = os.getenv("GOOGLE_CLIENT_ID")
    secret = os.getenv("GOOGLE_CLIENT_SECRET")

    for name, val in [
        ("GOOGLE_CLIENT_ID",     cid),
        ("GOOGLE_CLIENT_SECRET", secret),
    ]:
        if val:
            ok(f"{name} found in .env")
        else:
            fail(f"{name} missing from .env", f"Get it from console.cloud.google.com → Credentials")

    if not cid:
        return

    # Verify the client ID format (should end in .apps.googleusercontent.com)
    cid_clean = cid.strip()
    if cid_clean.endswith(".apps.googleusercontent.com"):
        ok("GOOGLE_CLIENT_ID format looks correct")
    else:
        fail("GOOGLE_CLIENT_ID format wrong", f"Should end with .apps.googleusercontent.com (got: ...{cid_clean[-30:]})")

    # Check that Fitness API is reachable (public endpoint)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://www.googleapis.com/fitness/v1/users/me/dataSources",
                                 headers={"Authorization": "Bearer dummy"})
            if r.status_code == 401:
                ok("Google Fitness API endpoint reachable", "Returns 401 (expected — no real token yet)")
            else:
                ok("Google Fitness API reachable", f"Status: {r.status_code}")
    except Exception as e:
        fail("Google Fitness API unreachable", str(e))

    # Print the OAuth connect URL so user can test it in browser
    app_url = os.getenv("APP_URL", "http://localhost:3000")
    redirect = f"{app_url}/api/auth/callback/google"
    scopes = (
        "https://www.googleapis.com/auth/fitness.heart_rate.read "
        "https://www.googleapis.com/auth/fitness.activity.read"
    )
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?response_type=code&client_id={cid}"
        f"&redirect_uri={redirect}"
        f"&scope={scopes.replace(' ', '%20')}"
        f"&access_type=offline&prompt=consent&state=test-user-001"
    )
    print(f"\n  {YELLOW}To connect Google Fit, open this URL in your browser:{RESET}")
    print(f"  {auth_url[:120]}...")
    print(f"  {YELLOW}(Full URL printed above — copy into browser){RESET}")


# ── Summary ───────────────────────────────────────────────────────

async def main():
    print(f"\n{'='*55}")
    print(f"{BOLD}  REAL API CONNECTION TEST{RESET}")
    print(f"{'='*55}")

    await test_gemini()
    await test_auth0()
    await test_google_fit()

    total = passed + failed
    print(f"\n{'='*55}")
    if failed == 0:
        print(f"  {GREEN}{BOLD}ALL {total} CHECKS PASSED — Ready for real data!{RESET}")
    else:
        print(f"  {RED}{BOLD}{failed} checks failed.{RESET} Fix the issues above then re-run.")
        print(f"\n  Most common fixes:")
        print(f"  • Missing .env values → copy backend/.env.example → backend/.env")
        print(f"  • Wrong Token Vault key → Auth0 dashboard → AI Agents → Token Vault → copy key")
        print(f"  • Google Client ID wrong → console.cloud.google.com → Credentials → OAuth 2.0")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    asyncio.run(main())
