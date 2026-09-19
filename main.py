"""
FastAPI backend for the Parkinson's Voice Screening research application.

Run with:
    uvicorn main:app --reload --port 8000

Then open http://localhost:8000 in a browser. The frontend (in ../frontend)
is served as static files by this same process, and talks to the API below
over fetch(). Everything under /api/* is the only thing you'd need to port
to a different frontend framework later.
"""

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import voice_pipeline

app = FastAPI(title="Parkinson's Voice Screening API")

# Wide-open CORS for local development. Tighten this to your real frontend
# origin before deploying anywhere outside localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# In-memory session history. This is intentionally NOT a database — it's a
# research prototype. History is real (built from actual submitted
# recordings in this server session), not mock data, but it resets when the
# server restarts. Swap this out for a real store (SQLite, etc.) if you need
# persistence across restarts.
_history: list[dict] = []


def _new_screening_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:4].upper()
    return f"SCR-{stamp}-{suffix}"


@app.get("/api/health")
def health():
    return {
        "status": "ok" if voice_pipeline.pipeline.loaded else "degraded",
        "model_loaded": voice_pipeline.pipeline.loaded,
        "detail": voice_pipeline.pipeline.load_error,
    }


@app.post("/api/screening")
async def create_screening(audio: UploadFile = File(...), patient_id: Optional[str] = Form(None)):
    suffix = Path(audio.filename or "recording.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
        result = voice_pipeline.run_screening(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if result["status"] == "error":
        raise HTTPException(status_code=422, detail=result["message"])

    screening_id = _new_screening_id()
    timestamp = datetime.now(timezone.utc).isoformat()
    patient_id = (patient_id or "").strip() or None

    record = {
        "screening_id": screening_id,
        "patient_id": patient_id,
        "timestamp": timestamp,
        "status": result["status"],
    }

    if result["status"] == "rejected":
        record["message"] = result["message"]
    else:
        record["audio"] = result["audio"]
        record["result"] = result["result"]
        record["features"] = result["features"]

    _history.insert(0, record)

    return record


@app.get("/api/history")
def get_history():
    return {"screenings": _history}


@app.get("/api/patients")
def list_patients():
    """
    Distinct patients seen in this session's history, with a screening count
    and the timestamp of their most recent screening. Only successfully
    completed ("ok") screenings count toward progress tracking.
    """
    by_patient: dict[str, dict] = {}
    for record in _history:
        pid = record.get("patient_id")
        if not pid or record["status"] != "ok":
            continue
        entry = by_patient.setdefault(pid, {"patient_id": pid, "screening_count": 0, "latest_timestamp": record["timestamp"]})
        entry["screening_count"] += 1
        if record["timestamp"] > entry["latest_timestamp"]:
            entry["latest_timestamp"] = record["timestamp"]

    patients = sorted(by_patient.values(), key=lambda p: p["latest_timestamp"], reverse=True)
    return {"patients": patients}


@app.get("/api/patients/{patient_id}/screenings")
def get_patient_screenings(patient_id: str):
    """All completed screenings for one patient, oldest first, for progress comparison."""
    screenings = [r for r in _history if r.get("patient_id") == patient_id and r["status"] == "ok"]
    screenings.sort(key=lambda r: r["timestamp"])
    if not screenings:
        raise HTTPException(status_code=404, detail="No completed screenings found for this patient ID.")
    return {"patient_id": patient_id, "screenings": screenings}


@app.delete("/api/history/{screening_id}")
def delete_history_item(screening_id: str):
    global _history
    before = len(_history)
    _history = [h for h in _history if h["screening_id"] != screening_id]
    if len(_history) == before:
        raise HTTPException(status_code=404, detail="Screening not found")
    return {"deleted": screening_id}


@app.get("/api/history/{screening_id}")
def get_history_item(screening_id: str):
    for h in _history:
        if h["screening_id"] == screening_id:
            return h
    raise HTTPException(status_code=404, detail="Screening not found")


# --- Serve the frontend as static files from the same process ---
if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
    app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")

    @app.get("/{page_name}.html")
    def serve_page(page_name: str):
        target = FRONTEND_DIR / f"{page_name}.html"
        if target.exists():
            return FileResponse(target)
        raise HTTPException(status_code=404)

    @app.get("/")
    def serve_index():
        return FileResponse(FRONTEND_DIR / "index.html")
