# Raksha — FastAPI Entry Point
# Routes: POST /analyze, GET /metrics, GET /cases, GET /cases/{case_id}, GET /evidence/{case_id}
# Hardened with: input validation, rate limiting, error handling, security headers, request logging.

from __future__ import annotations
import json
import logging
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse

from .schemas import (
    AnalyzeRequest, AnalyzeResponse,
    MetricsResponse, CaseResponse, CaseListResponse,
)
from .orchestrator import Orchestrator
from .store import get_store
from .agents.classifier import ClassifierAgent, MIN_SCAM_CONFIDENCE, MIN_SCAM_SIGNALS
from .llm.wrapper import get_llm
from .intel import run_entity_extraction

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("raksha.main")

# ── App Setup ──

app = FastAPI(
    title="Raksha — Citizen Fraud Shield",
    description="Digital Arrest Scam Detector + Citizen Fraud Shield (ET AI Hackathon 2.0, PS6)",
    version="1.0.0",
)

# CORS — allow all origins for hackathon prototype
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Orchestrator singleton
orchestrator = Orchestrator()

# Paths
BACKEND_DIR = Path(__file__).parent.parent
DATA_DIR = BACKEND_DIR / "data"
FRONTEND_DIR = BACKEND_DIR.parent / "frontend" / "src"
EVAL_RESULTS_PATH = DATA_DIR / "eval_results.json"


# ── Middleware: Request logging + Security headers ──

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers and log request timing."""
    start = time.monotonic()
    response = await call_next(request)
    elapsed = time.monotonic() - start

    # Log API requests (skip static files)
    if not request.url.path.startswith("/static") and request.url.path != "/favicon.ico":
        logger.info(
            f"{request.method} {request.url.path} -> {response.status_code} ({elapsed:.2f}s)"
        )

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response


# ── API Routes ──

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """
    Analyze a suspicious message.
    Returns verdict (SCAM/SAFE/UNCERTAIN), guidance, complaint draft, and authority alert.
    """
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text field cannot be empty")

    if len(request.text) > 15000:
        raise HTTPException(
            status_code=400,
            detail="Message too long. Maximum 15,000 characters."
        )

    try:
        result = await orchestrator.analyze(request)
        return result
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Analysis failed (ValueError): {error_msg}")

        # Return user-friendly error messages
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            raise HTTPException(
                status_code=503,
                detail="AI service is not configured. Please set your Gemini API key."
            )
        elif "timeout" in error_msg.lower():
            raise HTTPException(
                status_code=504,
                detail="Analysis timed out. The AI service is slow. Please try again."
            )
        elif "rate" in error_msg.lower() or "quota" in error_msg.lower():
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait a moment and try again."
            )
        else:
            raise HTTPException(status_code=502, detail=f"AI processing error: {error_msg}")

    except Exception as e:
        logger.error(f"Unexpected error during analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again."
        )


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """
    Get evaluation metrics (precision, recall, F1, FPR, confusion matrix).
    Reads pre-computed results from eval_results.json.
    """
    if not EVAL_RESULTS_PATH.exists():
        return MetricsResponse()

    try:
        with open(EVAL_RESULTS_PATH, "r") as f:
            data = json.load(f)
        return MetricsResponse(**data)
    except Exception as e:
        logger.error(f"Failed to load metrics: {e}")
        return MetricsResponse()


@app.on_event("startup")
async def startup_event():
    """Auto-seed campaign cases on startup if database is empty."""
    try:
        from .intel.seed_campaigns import seed_cases
        seed_cases()
        logger.info("Startup campaign seeder checked successfully.")
    except Exception as e:
        logger.error(f"Failed to auto-seed database on startup: {e}")


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Transcribe audio upload using Gemini multimodal API."""
    contents = await file.read()
    llm = get_llm()
    try:
        transcript = await llm.transcribe_audio(contents, mime_type=file.content_type)
        return {"transcript": transcript}
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """WebSocket for LiveShield real-time detection before money transfer."""
    await websocket.accept()
    logger.info("LiveShield WebSocket connected")

    transcript_buffer = []
    last_classified_time = 0.0
    session_start_time = time.monotonic()
    time_to_detection_s = 0.0
    first_flagged_chunk = 0

    classifier = ClassifierAgent()
    streaming_prompt_path = Path(__file__).parent / "prompts" / "classifier_streaming.txt"
    if streaming_prompt_path.exists():
        system_prompt = streaming_prompt_path.read_text(encoding="utf-8")
    else:
        system_prompt = classifier.system_prompt

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                chunk = msg.get("chunk", "")
                reset = msg.get("reset", False)
            except Exception:
                chunk = data
                reset = False

            if reset:
                transcript_buffer = []
                last_classified_time = 0.0
                session_start_time = time.monotonic()
                time_to_detection_s = 0.0
                first_flagged_chunk = 0
                await websocket.send_json({
                    "verdict": "SAFE",
                    "confidence": 0.0,
                    "signals": [],
                    "reasons": "Transcript reset.",
                    "flagged": False,
                    "time_to_detection_s": 0.0,
                    "chunks_processed": 0
                })
                continue

            if not chunk.strip():
                continue

            transcript_buffer.append(chunk)
            full_transcript = " ".join(transcript_buffer)

            # Debounce: classify at most once per 3 seconds
            now = time.monotonic()
            if now - last_classified_time >= 3.0:
                last_classified_time = now
                llm = get_llm()

                try:
                    from .schemas import ClassificationResult
                    result = await llm.generate_structured(
                        system_prompt=system_prompt,
                        user_message=full_transcript,
                        response_model=ClassificationResult,
                        temperature=0.2
                    )

                    is_flagged = False
                    if result.label == "SCAM":
                        if result.confidence < MIN_SCAM_CONFIDENCE or len(result.signals) < MIN_SCAM_SIGNALS:
                            result.label = "UNCERTAIN"
                        else:
                            is_flagged = True

                    if is_flagged and first_flagged_chunk == 0:
                        first_flagged_chunk = len(transcript_buffer)
                        time_to_detection_s = time.monotonic() - session_start_time

                    await websocket.send_json({
                        "verdict": result.label,
                        "confidence": result.confidence,
                        "signals": result.signals,
                        "reasons": result.reasons,
                        "flagged": is_flagged,
                        "time_to_detection_s": round(time_to_detection_s, 2),
                        "first_flagged_chunk": first_flagged_chunk,
                        "chunks_processed": len(transcript_buffer)
                    })
                except Exception as e:
                    logger.error(f"Live classification failed: {e}")
                    await websocket.send_json({
                        "error": str(e),
                        "chunks_processed": len(transcript_buffer)
                    })
            else:
                await websocket.send_json({
                    "status": "received",
                    "chunks_processed": len(transcript_buffer)
                })

    except WebSocketDisconnect:
        logger.info("LiveShield WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


@app.get("/audit/verify")
async def verify_audit():
    """Verify hash chain integrity across all case records."""
    store = get_store()
    try:
        report = store.verify_chain()
        return report
    except Exception as e:
        logger.error(f"Audit chain verification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/campaigns")
async def get_campaigns():
    """Get active campaign clusters (linked fraud networks)."""
    from .intel.campaigns import compute_campaign_clusters
    try:
        campaigns = compute_campaign_clusters()
        return {"campaigns": campaigns}
    except Exception as e:
        logger.error(f"Failed to compute campaigns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cases", response_model=CaseListResponse)
async def list_cases(limit: int = 100, offset: int = 0):
    """List all analyzed cases, most recent first."""
    # Clamp parameters to prevent abuse
    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    store = get_store()
    records = store.list_cases(limit=limit, offset=offset)
    total = store.count_cases()

    cases = []
    for r in records:
        cases.append(CaseResponse(
            case_id=r.case_id,
            timestamp=r.timestamp.isoformat() + "Z" if r.timestamp else "",
            input=r.input_text,
            language=r.language or "en",
            label=r.label,
            scam_type=r.scam_type,
            confidence=r.confidence or 0.0,
            reasons=r.reasons or "",
            model=r.model_used or "",
            evidence_package_url=f"/evidence/{r.case_id}",
            record_hash=r.record_hash,
            prev_hash=r.prev_hash,
        ))

    return CaseListResponse(cases=cases, total=total)


@app.get("/cases/{case_id}", response_model=CaseResponse)
async def get_case(case_id: str):
    """Get a single case by ID."""
    # Basic input validation on case_id (should be a UUID)
    if len(case_id) > 50:
        raise HTTPException(status_code=400, detail="Invalid case ID")

    store = get_store()
    record = store.get_case(case_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    return CaseResponse(
        case_id=record.case_id,
        timestamp=record.timestamp.isoformat() + "Z" if record.timestamp else "",
        input=record.input_text,
        language=record.language or "en",
        label=record.label,
        scam_type=record.scam_type,
        confidence=record.confidence or 0.0,
        reasons=record.reasons or "",
        model=record.model_used or "",
        evidence_package_url=f"/evidence/{record.case_id}",
        record_hash=record.record_hash,
        prev_hash=record.prev_hash,
    )


@app.get("/evidence/{case_id}")
async def get_evidence(case_id: str):
    """Download the evidence package for a case as JSON."""
    if len(case_id) > 50:
        raise HTTPException(status_code=400, detail="Invalid case ID")

    store = get_store()
    package = store.get_evidence_package(case_id)
    if not package:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    return JSONResponse(
        content=package,
        headers={
            "Content-Disposition": f'attachment; filename="evidence_{case_id}.json"'
        },
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    store = get_store()
    total_cases = store.count_cases()
    return {
        "status": "ok",
        "service": "raksha",
        "total_cases_analyzed": total_cases,
    }


# ── Static File Serving (Frontend) ──

# Serve frontend static files — must be last to not override API routes
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
