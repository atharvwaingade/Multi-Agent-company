"""
Crewpit Web Server

Features:
  - Serves the web UI at /
  - POST /run   — starts the pipeline (rate-limited: 1 concurrent run)
  - POST /cancel — cancels the current run
  - GET  /status — current server + Ollama health
  - SSE streaming of agent logs to the browser

Run:
    cd crewpit_patched
    python app/server.py
    open http://localhost:8000
"""

import sys
import os
import json
import asyncio
import queue
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("Missing deps — run: pip install fastapi uvicorn pydantic")
    sys.exit(1)

from app.config import OLLAMA_MODEL, PORT
from models.ollama_check import full_startup_check, is_ollama_running, get_local_models
from utils.logger import Logger


# ─── Global run state (one run at a time) ─────────────────────────────────────

class RunState:
    def __init__(self):
        self.lock        = threading.Lock()
        self.is_running  = False
        self.cancel_flag = threading.Event()   # set this to request cancellation
        self.log_queue   = queue.Queue()
        self.run_thread  = None
        self.started_at  = None

    def start(self) -> bool:
        """Try to acquire the run slot. Returns False if already occupied."""
        with self.lock:
            if self.is_running:
                return False
            self.is_running  = True
            self.cancel_flag.clear()
            self.log_queue   = queue.Queue()  # fresh queue per run
            self.started_at  = time.time()
            return True

    def finish(self):
        with self.lock:
            self.is_running = False
            self.started_at = None

    def request_cancel(self):
        self.cancel_flag.set()

    def is_cancelled(self) -> bool:
        return self.cancel_flag.is_set()


_run = RunState()


# ─── Patch Logger to push to the SSE queue ────────────────────────────────────

_original_log = Logger.log


class _StreamingLogger:
    COLORS = Logger.COLORS  # keep console colours

    @staticmethod
    def log(agent: str, message: str):
        # 1. Console output (original behaviour)
        import datetime
        ts    = datetime.datetime.now().strftime("%H:%M:%S")
        color = Logger.COLORS.get(agent, "")
        reset = Logger.COLORS["RESET"]
        print(f"{color}[{ts}] [{agent}] {message}{reset}", flush=True)

        # 2. Push to SSE queue for the browser
        _run.log_queue.put(json.dumps({
            "type":    "log",
            "agent":   agent,
            "message": message,
        }))


Logger.log = _StreamingLogger.log


# ─── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(title="Crewpit")


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    ui_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "index.html"
    )
    with open(ui_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/status")
async def status():
    ollama_ok, ollama_msg = is_ollama_running()
    models = get_local_models()
    elapsed = round(time.time() - _run.started_at, 1) if _run.started_at else None
    return JSONResponse({
        "ollama":      {"ok": ollama_ok, "message": ollama_msg},
        "model":       OLLAMA_MODEL,
        "local_models": models,
        "run": {
            "active":   _run.is_running,
            "elapsed_s": elapsed,
            "cancelled": _run.is_cancelled(),
        }
    })


class GoalRequest(BaseModel):
    goal: str


@app.post("/run")
async def run_endpoint(req: GoalRequest):
    """
    Start a Crewpit pipeline run.
    Returns 409 if a run is already in progress.
    Streams agent logs as SSE events.
    """
    goal = req.goal.strip()
    if not goal:
        raise HTTPException(status_code=400, detail="Goal cannot be empty")

    # ── Rate limit: one run at a time ─────────────────────────────────────────
    if not _run.start():
        elapsed = round(time.time() - (_run.started_at or time.time()), 1)
        raise HTTPException(
            status_code=409,
            detail=f"A run is already in progress ({elapsed}s elapsed). "
                   "POST /cancel to stop it first."
        )

    # ── Check Ollama before starting ──────────────────────────────────────────
    ok, msg = full_startup_check(OLLAMA_MODEL)
    if not ok:
        _run.finish()
        raise HTTPException(status_code=503, detail=msg)

    # ── Run pipeline in background thread ─────────────────────────────────────
    def pipeline_thread():
        try:
            from app.main import run_crewpit
            out = run_crewpit(goal, cancel_flag=_run.cancel_flag)

            if _run.is_cancelled():
                _run.log_queue.put(json.dumps({
                    "type":    "cancelled",
                    "message": "Run was cancelled by user",
                }))
                return

            # Emit file list
            if out and os.path.isdir(out):
                for fname in sorted(os.listdir(out)):
                    fpath    = os.path.join(out, fname)
                    size     = os.path.getsize(fpath)
                    size_str = f"{size/1024:.1f} KB" if size > 1024 else f"{size} B"
                    _run.log_queue.put(json.dumps({
                        "type": "file",
                        "name": fname,
                        "size": size_str,
                        "path": fpath,
                    }))

            _run.log_queue.put(json.dumps({
                "type":       "done",
                "output_dir": out or "",
            }))

        except Exception as e:
            Logger.log("SYSTEM", f"❌ Pipeline error: {e}")
            _run.log_queue.put(json.dumps({
                "type":    "error",
                "message": str(e),
            }))
        finally:
            _run.finish()

    t = threading.Thread(target=pipeline_thread, daemon=True)
    t.start()
    _run.run_thread = t

    # ── Stream SSE to browser ─────────────────────────────────────────────────
    async def event_stream():
        loop = asyncio.get_event_loop()
        sentinel_types = {"done", "error", "cancelled"}

        while True:
            try:
                msg = await loop.run_in_executor(
                    None, lambda: _run.log_queue.get(timeout=0.1)
                )
                yield f"data: {msg}\n\n"

                # Stop streaming after terminal event
                try:
                    if json.loads(msg).get("type") in sentinel_types:
                        break
                except Exception:
                    pass

            except queue.Empty:
                # Send a keepalive comment so the connection doesn't time out
                if not _run.is_running and _run.log_queue.empty():
                    break
                yield ": keepalive\n\n"
                await asyncio.sleep(0.1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )


@app.post("/cancel")
async def cancel_endpoint():
    """Request cancellation of the current run."""
    if not _run.is_running:
        return JSONResponse({"ok": False, "message": "No run is active"})
    _run.request_cancel()
    Logger.log("SYSTEM", "🛑 Cancellation requested by user")
    return JSONResponse({"ok": True, "message": "Cancellation requested"})


# ─── Startup check ────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_check():
    print("\n" + "─" * 50)
    ok, msg = full_startup_check(OLLAMA_MODEL)
    if ok:
        print(f"  {msg}")
    else:
        print(f"  {msg}")
        print(f"\n  ⚠️  Server will start but runs will fail until Ollama is ready.")
        print(f"  Fix: ollama serve   then:   ollama pull {OLLAMA_MODEL}")
    print("─" * 50 + "\n")


if __name__ == "__main__":
    print(f"\n🤖 Crewpit UI → http://localhost:{PORT}\n")
    uvicorn.run(
        "app.server:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        log_level="warning",   # suppress uvicorn noise; we have our own logger
    )
