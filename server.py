"""Palimpsest — Web server with real-time progress via WebSocket."""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("palimpsest.server")

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Palimpsest", version="0.1.0")

# ── State ────────────────────────────────────────────────

jobs: dict[str, dict] = {}  # job_id -> {status, progress, total, stage, output_path, error, timestamp}
websockets: dict[str, list[WebSocket]] = {}  # job_id -> connected websockets
JOBS_DB_PATH = BASE_DIR / ".cache/jobs_history.json"


def _load_jobs_db():
    """Load jobs history from disk."""
    if JOBS_DB_PATH.exists():
        try:
            with open(JOBS_DB_PATH) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load jobs DB: {e}")
    return {}


def _save_job_to_db(job_id: str, job_data: dict):
    """Persist a job record to disk."""
    JOBS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    history = _load_jobs_db()
    history[job_id] = job_data
    try:
        with open(JOBS_DB_PATH, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save job {job_id}: {e}")


# Load jobs from history on startup
jobs = _load_jobs_db()


async def broadcast(job_id: str, data: dict):
    """Send progress update to all connected clients for a job."""
    for ws in websockets.get(job_id, []):
        try:
            await ws.send_json(data)
        except Exception:
            pass


# ── Routes ───────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return (BASE_DIR / "web/index.html").read_text(encoding="utf-8")


@app.get("/favicon.svg")
async def favicon():
    return FileResponse(BASE_DIR / "web/favicon.svg", media_type="image/svg+xml")


@app.post("/api/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    model: str = Form("o4-mini"),
    send_image: str = Form("true"),
    engine: str = Form("vision"),
):
    """Upload a PDF and start processing."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return {"error": "Only PDF files are accepted."}

    job_id = str(uuid.uuid4())[:8]
    upload_dir = BASE_DIR / "uploads"
    upload_dir.mkdir(exist_ok=True)

    # Save uploaded file
    safe_name = Path(file.filename).name  # sanitize
    pdf_path = upload_dir / f"{job_id}_{safe_name}"
    content = await file.read()
    pdf_path.write_bytes(content)

    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "filename": safe_name,
        "model": model,
        "send_image": send_image == "true",
        "engine": engine,
        "progress": 0,
        "total": 0,
        "stage": "queued",
        "output_path": None,
        "error": None,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    _save_job_to_db(job_id, jobs[job_id])

    # Start processing in background
    asyncio.create_task(_process_job(job_id, str(pdf_path), model, send_image == "true", engine))

    return {"job_id": job_id, "filename": safe_name}


async def _process_job(job_id: str, pdf_path: str, model: str = "o4-mini", send_image: bool = True, engine: str = "vision"):
    """Background task to run the pipeline."""
    jobs[job_id]["status"] = "processing"

    def on_progress(page: int, total: int, stage: str):
        jobs[job_id].update(progress=page, total=total, stage=stage)
        asyncio.create_task(broadcast(job_id, {
            "type": "progress",
            "page": page,
            "total": total,
            "stage": stage,
        }))

    try:
        # Create a temporary config with the chosen model
        config_path = BASE_DIR / "config.yaml"
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text())
        else:
            config = yaml.safe_load((BASE_DIR / "config.example.yaml").read_text())
        config.setdefault("rewrite", {})["model"] = model
        config.setdefault("rewrite", {})["send_source_image"] = send_image
        config.setdefault("extraction", {})["engine"] = engine

        tmp_config = BASE_DIR / f".cache/_web_config_{job_id}.yaml"
        tmp_config.parent.mkdir(parents=True, exist_ok=True)
        tmp_config.write_text(yaml.dump(config))

        output = await run_pipeline(pdf_path, config_path=str(tmp_config), on_progress=on_progress)

        # Clean up temp config
        tmp_config.unlink(missing_ok=True)

        jobs[job_id]["status"] = "done"
        jobs[job_id]["output_path"] = str(output)
        jobs[job_id]["has_pdf"] = output.suffix == ".pdf"
        _save_job_to_db(job_id, jobs[job_id])
        await broadcast(job_id, {"type": "done", "output": str(output), "has_pdf": output.suffix == ".pdf"})
    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
        _save_job_to_db(job_id, jobs[job_id])
        await broadcast(job_id, {"type": "error", "message": str(e)})


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """Get current status of a job."""
    if job_id not in jobs:
        return {"error": "Job not found."}
    return jobs[job_id]


@app.get("/api/jobs/{job_id}/download")
async def download_result(job_id: str, fmt: str = "auto"):
    """Download the result — PDF if available, otherwise .tex.

    Query params:
        fmt: "pdf", "tex", or "auto" (default: prefer PDF).
    """
    if job_id not in jobs:
        return {"error": "Job not found."}
    job = jobs[job_id]
    if job["status"] != "done" or not job["output_path"]:
        return {"error": "Job not ready."}
    path = Path(job["output_path"])

    # If user explicitly requests tex, or the output is already tex
    if fmt == "tex":
        tex_path = path.with_suffix(".tex") if path.suffix == ".pdf" else path
        if tex_path.exists():
            return FileResponse(tex_path, filename=tex_path.name, media_type="application/x-tex")

    # Default: prefer PDF
    if path.suffix == ".pdf" and path.exists():
        return FileResponse(path, filename=path.name, media_type="application/pdf")

    # fmt=pdf requested but only .tex exists → compilation failed; honest error
    if fmt == "pdf":
        tex_path = path.with_suffix(".tex") if path.suffix == ".pdf" else path
        if tex_path.exists():
            return {"error": "pdf_unavailable", "detail": "La compilation LaTeX a échoué sur le serveur. Téléchargez le .tex et compilez sur Overleaf."}
        return {"error": "Output file not found."}

    # Fallback: serve .tex
    tex_path = path.with_suffix(".tex") if path.suffix == ".pdf" else path
    if tex_path.exists():
        return FileResponse(tex_path, filename=tex_path.name, media_type="application/x-tex")
    return {"error": "Output file not found."}


@app.get("/api/jobs/list")
async def list_jobs(limit: int = 50, status: str = None):
    """List all jobs sorted by timestamp (newest first)."""
    job_list = sorted(
        jobs.values(),
        key=lambda x: x.get("timestamp", ""),
        reverse=True
    )
    if status:
        job_list = [j for j in job_list if j.get("status") == status]
    if limit:
        job_list = job_list[:limit]
    return {"jobs": job_list, "total": len(job_list)}


@app.get("/api/jobs/latest")
async def latest_job():
    """Get the most recent job (by timestamp)."""
    if not jobs:
        return {"error": "No jobs found."}
    latest = max(jobs.values(), key=lambda x: x.get("timestamp", ""))
    return latest


@app.websocket("/ws/{job_id}")
async def ws_progress(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time progress updates."""
    await websocket.accept()
    websockets.setdefault(job_id, []).append(websocket)

    # Send current state immediately
    if job_id in jobs:
        await websocket.send_json({"type": "status", **jobs[job_id]})

    try:
        while True:
            await websocket.receive_text()  # Keep alive
    except WebSocketDisconnect:
        websockets.get(job_id, []).remove(websocket)


# ── Main ─────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
