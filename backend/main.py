"""
FastAPI Backend — Health Advocate Agent
========================================
Adds real Google Fit OAuth routes on top of the existing agent endpoints.

New routes:
  GET  /api/auth/google?user_id=xxx        → redirects to Google consent
  GET  /api/auth/callback/google           → handles OAuth callback, stores tokens
  GET  /api/connection-status?user_id=xxx  → checks which services are connected
"""

from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
import uvicorn

from watcher import watch_user, stop_watching
from agent import run_agent
from vault import revoke_vault_token, list_connected_services
from stepup import stepup_callback_handler, check_step_up
from oauth import (
    build_google_auth_url,
    exchange_code_for_tokens,
    store_tokens_in_vault,
)

app = FastAPI(title="Health Advocate Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

active_watchers = {}


# ── Models ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    user_id: str
    message: str


class WatchRequest(BaseModel):
    user_id: str
    threshold_bpm: int = 100


# ── Google OAuth Routes ───────────────────────────────────────────────────────

@app.get("/api/auth/google")
async def google_auth_start(user_id: str = Query(..., description="User ID to associate tokens with")):
    """
    Step 1: Redirect the user to Google's OAuth consent screen.
    The user_id is passed as state so we know who to store tokens for.
    """
    auth_url = build_google_auth_url(user_id)
    return RedirectResponse(url=auth_url)


@app.get("/api/auth/callback/google")
async def google_auth_callback(
    code: str = Query(None),
    state: str = Query(None),   # This is our user_id
    error: str = Query(None),
):
    """
    Step 2: Google redirects here after user approves permissions.
    We exchange the code for tokens and store them in Auth0 Token Vault.
    """
    if error:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": f"OAuth denied: {error}"}
        )

    if not code or not state:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Missing code or state parameter"}
        )

    user_id = state

    try:
        # Exchange authorization code for real tokens
        tokens = await exchange_code_for_tokens(code)
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")

        if not access_token:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "No access token in response"}
            )

        # Store securely in Auth0 Token Vault
        await store_tokens_in_vault(user_id, access_token, refresh_token)

        # Redirect back to frontend settings page with success flag
        import os
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        return RedirectResponse(url=f"{frontend_url}/settings?connected=google_fit")

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Token exchange failed: {str(e)}"}
        )


# ── Connection Status ─────────────────────────────────────────────────────────

@app.get("/api/connection-status")
async def connection_status(user_id: str = Query(...)):
    """
    Returns which services the user has connected.
    Used by the frontend settings page to show Connect/Disconnect buttons.
    """
    try:
        connected = await list_connected_services(user_id)

        # Also check if Google Fit has a valid live token
        google_fit_live = False
        try:
            from oauth import get_valid_access_token
            token = await get_valid_access_token(user_id)
            google_fit_live = token is not None
        except Exception:
            pass

        return {
            "user_id": user_id,
            "connected_services": connected,
            "google_fit_live": google_fit_live,
        }
    except Exception as e:
        return {"user_id": user_id, "connected_services": [], "error": str(e)}


# ── Existing Agent Routes ─────────────────────────────────────────────────────

@app.post("/api/start-watching")
async def start_watching(req: WatchRequest, bg: BackgroundTasks):
    if req.user_id in active_watchers:
        return {"status": "already_watching"}
    bg.add_task(watch_user, req.user_id, req.threshold_bpm)
    active_watchers[req.user_id] = True
    return {"status": "watching", "threshold_bpm": req.threshold_bpm}


@app.post("/api/stop-watching")
async def stop_watching_route(user_id: str):
    stop_watching(user_id)
    active_watchers.pop(user_id, None)
    return {"status": "stopped"}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        response = await run_agent(req.user_id, req.message)
        return JSONResponse(content={"response": response})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"response": {"status": "error", "response": f"Error: {str(e)}"}}
        )


@app.get("/api/stepup-status")
async def stepup_status(user_id: str):
    active = check_step_up(user_id)
    return {"step_up_active": active}


@app.get("/stepup/callback")
async def stepup_callback(code: str, state: str):
    result = await stepup_callback_handler(code, state)
    return result


@app.delete("/api/revoke/{service}")
async def revoke(user_id: str, service: str):
    await revoke_vault_token(user_id, service)
    return {"status": "revoked", "service": service}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)