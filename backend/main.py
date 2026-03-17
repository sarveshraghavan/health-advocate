from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from watcher import watch_user, stop_watching
from agent import run_agent
from vault import revoke_vault_token
from stepup import stepup_callback_handler, check_step_up

app = FastAPI(title="Health Advocate Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

active_watchers = {}

class ChatRequest(BaseModel):
    user_id: str
    message: str

class WatchRequest(BaseModel):
    user_id: str
    threshold_bpm: int = 100

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
    # FIX 1: Wrap in try/except and use JSONResponse so CORS headers
    # are always present — even on internal errors.
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
