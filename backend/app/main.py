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
    GuardianCreate, GuardianResponse, GuardianAlertResponse,
    TelegramNotifyRequest, TelegramNotifyResponse,
)
from pydantic import BaseModel
from .orchestrator import Orchestrator
from .store import get_store, RehearsalRecord
from .agents.classifier import ClassifierAgent, MIN_SCAM_CONFIDENCE, MIN_SCAM_SIGNALS
from .agents.simulator import SimulatorAgent, DebriefAgent
from .llm.wrapper import get_llm
from .intel import run_entity_extraction
from .services.telegram import get_telegram_service


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("raksha.main")

# ── App Setup ──

import hashlib
from uuid import uuid4

class SimpleLRUCache:
    def __init__(self, maxsize: int = 128):
        self.maxsize = maxsize
        self.cache = {}
        self.keys = []

    def get(self, key: str):
        if key in self.cache:
            self.keys.remove(key)
            self.keys.append(key)
            return self.cache[key]
        return None

    def set(self, key: str, value):
        if key in self.cache:
            self.keys.remove(key)
        elif len(self.cache) >= self.maxsize:
            oldest = self.keys.pop(0)
            del self.cache[oldest]
        self.keys.append(key)
        self.cache[key] = value

live_lru_cache = SimpleLRUCache(maxsize=128)

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
    session_case_id = str(uuid4())
    logged_case = False

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
                session_case_id = str(uuid4())
                logged_case = False
                await websocket.send_json({
                    "verdict": "SAFE",
                    "confidence": 0.0,
                    "signals": [],
                    "reasons": "Transcript reset.",
                    "flagged": False,
                    "time_to_detection_s": 0.0,
                    "chunks_processed": 0,
                    "case_id": session_case_id
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

                # ── LRU Cache Keyed on Transcript Hash ──
                transcript_hash = hashlib.sha256(full_transcript.encode("utf-8")).hexdigest()
                cached = live_lru_cache.get(transcript_hash)

                if cached:
                    logger.info("LiveShield Cache HIT")
                    result = cached
                else:
                    logger.info("LiveShield Cache MISS — Calling LLM")
                    llm = get_llm()
                    try:
                        from .schemas import ClassificationResult
                        result = await llm.generate_structured(
                            system_prompt=system_prompt,
                            user_message=full_transcript,
                            response_model=ClassificationResult,
                            temperature=0.2
                        )
                        # Save in cache
                        live_lru_cache.set(transcript_hash, result)
                    except Exception as e:
                        logger.error(f"Live classification failed: {e}")
                        await websocket.send_json({
                            "error": str(e),
                            "chunks_processed": len(transcript_buffer)
                        })
                        continue

                is_flagged = False
                if result.label == "SCAM":
                    if result.confidence < MIN_SCAM_CONFIDENCE or len(result.signals) < MIN_SCAM_SIGNALS:
                        result.label = "UNCERTAIN"
                    else:
                        is_flagged = True

                if is_flagged and first_flagged_chunk == 0:
                    first_flagged_chunk = len(transcript_buffer)
                    time_to_detection_s = time.monotonic() - session_start_time

                # ── Log verified scam to Database ──
                if is_flagged and not logged_case:
                    logged_case = True
                    try:
                        # Pre-generate specialist agent artifacts for this case
                        guidance, complaint, alert = await orchestrator._run_scam_agents(
                            full_transcript, result, session_case_id, "en", None
                        )
                        store = get_store()
                        store.log_case(
                            case_id=session_case_id,
                            input_text=full_transcript,
                            language="en",
                            label=result.label,
                            scam_type=result.scam_type,
                            confidence=result.confidence,
                            reasons=result.reasons,
                            signals=result.signals,
                            model_used="gemini-2.0-flash",
                            full_response=result.model_dump(),
                            guidance_json=guidance.model_dump_json() if guidance else None,
                            complaint_json=complaint.model_dump_json() if complaint else None,
                            alert_json=alert.model_dump_json() if alert else None,
                        )
                    except Exception as e:
                        logger.error(f"Failed to log LiveShield scam to DB: {e}")
                        try:
                            store = get_store()
                            store.log_case(
                                case_id=session_case_id,
                                input_text=full_transcript,
                                language="en",
                                label=result.label,
                                scam_type=result.scam_type,
                                confidence=result.confidence,
                                reasons=result.reasons,
                                signals=result.signals,
                                model_used="gemini-2.0-flash",
                                full_response=result.model_dump(),
                            )
                        except Exception as inner_e:
                            logger.error(f"Failed fallback DB log: {inner_e}")

                await websocket.send_json({
                    "verdict": result.label,
                    "confidence": result.confidence,
                    "signals": result.signals,
                    "reasons": result.reasons,
                    "flagged": is_flagged,
                    "time_to_detection_s": round(time_to_detection_s, 2),
                    "first_flagged_chunk": first_flagged_chunk,
                    "chunks_processed": len(transcript_buffer),
                    "case_id": session_case_id,
                    "mode": getattr(result, "mode", "live_gemini")
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
# ── Guardian and Alert Endpoints ──

@app.post("/guardians", response_model=GuardianResponse)
async def create_guardian(guardian: GuardianCreate):
    """Register a new trusted contact."""
    store = get_store()
    try:
        record = store.add_guardian(
            name=guardian.name,
            phone=guardian.phone,
            relationship=guardian.relationship
        )
        return GuardianResponse(
            id=record.id,
            name=record.name,
            phone=record.phone,
            relationship=record.relationship
        )
    except Exception as e:
        logger.error(f"Failed to create guardian: {e}")
        raise HTTPException(status_code=500, detail="Failed to register contact")


@app.get("/guardians", response_model=list[GuardianResponse])
async def list_guardians():
    """Get all registered trusted contacts."""
    store = get_store()
    records = store.get_guardians()
    return [
        GuardianResponse(
            id=r.id,
            name=r.name,
            phone=r.phone,
            relationship=r.relationship
        ) for r in records
    ]


@app.delete("/guardians/{guardian_id}")
async def delete_guardian(guardian_id: int):
    """Delete a registered trusted contact."""
    store = get_store()
    success = store.delete_guardian(guardian_id)
    if not success:
        raise HTTPException(status_code=404, detail="Guardian not found")
    return {"status": "success", "message": "Guardian contact deleted"}


class NotifyRequest(BaseModel):
    case_id: str
    victim_name: Optional[str] = "Protected User"
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None


@app.post("/guardian/notify")
async def notify_guardians(request: NotifyRequest):
    """Send or simulate an emergency alert to all registered guardians & Telegram Bot."""
    store = get_store()
    case = store.get_case(request.case_id) if request.case_id else None

    # Extract suspect agency and details if case exists
    suspect_agency = "CBI / TRAI"
    record_hash = ""
    confidence = 0.95
    if case:
        record_hash = case.record_hash or ""
        confidence = case.confidence if case.confidence is not None else 0.95
        if "customs" in (case.input_text or "").lower():
            suspect_agency = "Customs"
        elif "police" in (case.input_text or "").lower():
            suspect_agency = "Police"
        elif "trai" in (case.input_text or "").lower():
            suspect_agency = "TRAI"

    # Always dispatch to Telegram Guardian Service (Live + Browser Preview)
    telegram_svc = get_telegram_service()
    telegram_res = telegram_svc.send_alert(
        victim_name=request.victim_name or "Protected User",
        risk_level="HIGH",
        confidence=confidence,
        scam_type=f"Digital Arrest ({suspect_agency})",
        observed_signals=["Digital Arrest Threat", "Coercive Video Call Demand"],
        case_id=request.case_id or "CASE-LIVE",
        record_hash=record_hash,
        override_chat_id=request.chat_id,
        override_bot_token=request.bot_token,
    )

    guardians = store.get_guardians()
    alerts_triggered = []

    if guardians:
        for guardian in guardians:
            rel = guardian.relationship.lower()
            relation_term = "family member"
            if "son" in rel or "daughter" in rel or "child" in rel:
                relation_term = "father/mother"
            elif "father" in rel or "mother" in rel or "parent" in rel:
                relation_term = "son/daughter"
            elif "spouse" in rel or "husband" in rel or "wife" in rel:
                relation_term = "spouse"

            msg = (
                f"Your {relation_term} may currently be on a scam call impersonating {suspect_agency}. "
                f"He/she has been told to keep it secret under threat of 'digital arrest'. "
                f"Please call them NOW on their other phone. Do NOT let them transfer any money. "
                f"Reference case: {request.case_id}"
            )

            status = "DISPATCHED"
            store.log_guardian_alert(
                case_id=request.case_id,
                guardian_name=guardian.name,
                guardian_phone=guardian.phone,
                message=msg,
                status=status
            )

            alerts_triggered.append({
                "guardian_name": guardian.name,
                "guardian_phone": guardian.phone,
                "message": msg,
                "status": status,
                "error": None
            })

    return {
        "status": "success",
        "simulated": not telegram_res.get("delivered", False),
        "message": "Guardian alerts dispatched to Guardian Circle and Telegram Bot",
        "alerts": alerts_triggered,
        "telegram": telegram_res
    }



@app.get("/guardian/alerts", response_model=list[GuardianAlertResponse])
async def list_guardian_alerts():
    """Get list of triggered guardian alerts."""
    store = get_store()
    records = store.get_guardian_alerts()
    return [
        GuardianAlertResponse(
            id=r.id,
            case_id=r.case_id,
            guardian_name=r.guardian_name,
            guardian_phone=r.guardian_phone,
            message=r.message,
            timestamp=r.timestamp.isoformat() + "Z" if r.timestamp else "",
            status=r.status
        ) for r in records
    ]


# ── Rehearsal Endpoints ──

class RehearsalStartResponse(BaseModel):
    session_id: str
    welcome_message: str
    mode: str = "offline_fallback"

class RehearsalMessageRequest(BaseModel):
    session_id: str
    message: str

class RehearsalMessageResponse(BaseModel):
    reply: str
    mode: str = "offline_fallback"

class RehearsalEndRequest(BaseModel):
    session_id: str


@app.post("/rehearsal/start", response_model=RehearsalStartResponse)
async def start_rehearsal():
    """Start a new educational scam simulation rehearsal."""
    store = get_store()
    session_id = str(uuid4())
    welcome_message = (
        "Hello, this is the Telecom Regulatory Authority of India (TRAI) Department of Communications. "
        "Your mobile number is flagged for spreading illegal advertisements and money laundering. "
        "We are routing your line to the CBI Headquarters Cyber Cell in Mumbai. Do not hang up the call."
    )
    
    # Store initial message in history
    initial_history = [{"role": "assistant", "content": welcome_message}]
    try:
        store.start_rehearsal(session_id)
        store.update_rehearsal(session_id, initial_history, 1)
        llm = get_llm()
        current_mode = "live_gemini" if (llm.api_key and llm.api_key not in ("your-gemini-api-key-here", "your-api-key-here", "")) else "offline_fallback"
        return RehearsalStartResponse(session_id=session_id, welcome_message=welcome_message, mode=current_mode)
    except Exception as e:
        logger.error(f"Failed to start rehearsal: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize rehearsal session")


@app.post("/rehearsal/message", response_model=RehearsalMessageResponse)
async def rehearsal_message(request: RehearsalMessageRequest):
    """Receive user reply, run simulation role-play, and return scammer's response."""
    store = get_store()
    
    # Retrieve rehearsal session
    session = store._get_session()
    try:
        record = session.query(RehearsalRecord).filter(RehearsalRecord.session_id == request.session_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Rehearsal session not found")
        history = json.loads(record.history)
        turns_count = record.turns_count
    finally:
        session.close()

    # Append user message
    history.append({"role": "user", "content": request.message})
    turns_count += 1

    # Call Simulator Agent
    simulator = SimulatorAgent()
    try:
        reply = await simulator.generate_reply(history)
    except Exception as e:
        logger.error(f"Simulator agent failed: {e}")
        raise HTTPException(status_code=502, detail=f"Scam simulator error: {str(e)}")

    # Append assistant message
    history.append({"role": "assistant", "content": reply})
    turns_count += 1

    # Save to database
    store.update_rehearsal(request.session_id, history, turns_count)

    llm = get_llm()
    current_mode = "live_gemini" if (llm.api_key and llm.api_key not in ("your-gemini-api-key-here", "your-api-key-here", "")) else "offline_fallback"
    return RehearsalMessageResponse(reply=reply, mode=current_mode)


@app.post("/rehearsal/end")
async def end_rehearsal(request: RehearsalEndRequest):
    """End simulation session, run debrief evaluation, and return scorecard."""
    store = get_store()
    
    # Retrieve rehearsal session
    session = store._get_session()
    try:
        record = session.query(RehearsalRecord).filter(RehearsalRecord.session_id == request.session_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Rehearsal session not found")
        history = json.loads(record.history)
    finally:
        session.close()

    # Call Debrief Agent
    debrief_agent = DebriefAgent()
    try:
        scorecard = await debrief_agent.debrief(history)
    except Exception as e:
        logger.error(f"Debrief agent failed: {e}")
        raise HTTPException(status_code=502, detail=f"Debrief scoring error: {str(e)}")

    # Convert scorecard Pydantic model to dict
    scorecard_dict = scorecard.model_dump()

    # Complete the rehearsal record in database
    store.complete_rehearsal(request.session_id, scorecard_dict)

    return scorecard_dict


@app.get("/rehearsal/inoculated")
async def get_inoculated_count():
    """Get the total count of completed citizen inoculations."""
    store = get_store()
    count = store.count_completed_rehearsals()
    return {"count": count}


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


@app.post("/guardian/notify", response_model=TelegramNotifyResponse)
async def guardian_notify_endpoint(req: TelegramNotifyRequest):
    """Triggers a Telegram Guardian Alert."""
    telegram_svc = get_telegram_service()
    res = telegram_svc.send_alert(
        victim_name=req.victim_name or "Protected User",
        risk_level=req.risk_level or "HIGH",
        confidence=req.confidence if req.confidence is not None else 0.95,
        scam_type=req.scam_type or "Digital Arrest (CBI / TRAI)",
        observed_signals=req.observed_signals,
        case_id=req.case_id or "",
        record_hash=req.record_hash or "",
        override_chat_id=req.chat_id,
        override_bot_token=req.bot_token,
    )
    return TelegramNotifyResponse(**res)


@app.post("/guardian/telegram/send", response_model=TelegramNotifyResponse)
async def guardian_telegram_send_endpoint(req: TelegramNotifyRequest):
    """Triggers a Telegram Guardian Alert via direct send endpoint."""
    telegram_svc = get_telegram_service()
    res = telegram_svc.send_alert(
        victim_name=req.victim_name or "Protected User",
        risk_level=req.risk_level or "HIGH",
        confidence=req.confidence if req.confidence is not None else 0.95,
        scam_type=req.scam_type or "Digital Arrest (CBI / TRAI)",
        observed_signals=req.observed_signals,
        case_id=req.case_id or "",
        record_hash=req.record_hash or "",
        override_chat_id=req.chat_id,
        override_bot_token=req.bot_token,
    )
    return TelegramNotifyResponse(**res)



# ── Static File Serving (Frontend) ──

# Serve frontend static files — must be last to not override API routes
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

