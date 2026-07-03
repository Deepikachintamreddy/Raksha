# Raksha — Orchestrator
# Language detection, deterministic routing, concurrent agent execution, and reply fusion.

from __future__ import annotations
import asyncio
import json
import logging
import os
import time
from typing import Optional
from uuid import uuid4

from langdetect import detect, LangDetectException

from .schemas import (
    AnalyzeRequest, AnalyzeResponse, ClassificationResult,
    GuidanceResult, ComplaintDraft, AuthorityAlert,
)
from .agents.classifier import ClassifierAgent
from .agents.guidance import GuidanceAgent
from .agents.complaint import ComplaintAgent
from .agents.alert import AlertAgent
from .store import get_store
from .llm.wrapper import sanitize_input

logger = logging.getLogger("raksha.orchestrator")

# Language code mapping — langdetect uses ISO 639-1
LANG_MAP = {
    "en": "en",
    "hi": "hi",
    "te": "te",
    "kn": "kn",
    # Common langdetect codes that map to our supported languages
    "mr": "hi",  # Marathi often detected for Hinglish, fall back to Hindi
    "ur": "hi",  # Urdu script often overlaps with Hindi
}

# Default language if detection fails
DEFAULT_LANG = "en"


def detect_language(text: str) -> str:
    """Detect the language of the input text. Returns en|hi|te|kn."""
    try:
        detected = detect(text)
        lang = LANG_MAP.get(detected, DEFAULT_LANG)
        logger.info(f"Language detected: {detected} -> mapped to: {lang}")
        return lang
    except LangDetectException:
        logger.warning("Language detection failed, defaulting to 'en'")
        return DEFAULT_LANG


class Orchestrator:
    """
    The brain of Raksha.
    Routes input through specialist agents based on classification result:
      - SCAM      -> Classifier + Guidance + Complaint + Alert  (run concurrently)
      - UNCERTAIN -> Classifier + Guidance only
      - SAFE      -> Classifier only (brief reassurance)
    """

    def __init__(self):
        self.classifier = ClassifierAgent()
        self.guidance = GuidanceAgent()
        self.complaint = ComplaintAgent()
        self.alert = AlertAgent()

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """Full analysis pipeline: validate -> classify -> route -> fuse -> log -> respond."""
        start_time = time.monotonic()
        case_id = str(uuid4())

        # 1. Sanitize input
        text = sanitize_input(request.text)

        # 2. Detect language
        language = detect_language(text)
        logger.info(f"Case {case_id}: language={language}, text_length={len(text)}")

        # 3. Classify
        classification = await self.classifier.classify(text)
        logger.info(f"Case {case_id}: verdict={classification.label}")

        # 4. Route based on label — run downstream agents CONCURRENTLY for speed
        guidance: Optional[GuidanceResult] = None
        complaint: Optional[ComplaintDraft] = None
        authority_alert: Optional[AuthorityAlert] = None

        if classification.label == "SCAM":
            # Run all 3 specialist agents concurrently
            guidance, complaint, authority_alert = await self._run_scam_agents(
                text, classification, case_id, language, request.user_details
            )
        elif classification.label == "UNCERTAIN":
            # Guidance only (verification-focused)
            guidance = await self._safe_agent_call(
                "Guidance",
                self.guidance.generate(text, classification),
            )

        # 5. Build reply text
        reply_text = self._build_reply(language, classification, guidance)

        # 6. Build response
        response = AnalyzeResponse(
            case_id=case_id,
            language=language,
            verdict=classification.label,
            reply_text=reply_text,
            classification=classification,
            guidance=guidance,
            complaint_draft=complaint,
            authority_alert=authority_alert,
        )

        # 7. Log to audit store (fire-and-forget, never block the response)
        await self._log_case(case_id, text, language, classification, response,
                             guidance, complaint, authority_alert)

        elapsed = time.monotonic() - start_time
        logger.info(f"Case {case_id}: completed in {elapsed:.2f}s")

        return response

    async def _run_scam_agents(
        self,
        text: str,
        classification: ClassificationResult,
        case_id: str,
        language: str,
        user_details,
    ) -> tuple[Optional[GuidanceResult], Optional[ComplaintDraft], Optional[AuthorityAlert]]:
        """Run all SCAM-path agents sequentially to avoid rate limiting."""
        # Free-tier safe execution: Run sequentially instead of concurrently
        # asyncio.gather() triggers 3 simultaneous requests which causes 429 Too Many Requests
        # on Gemini free tier.
        
        guidance = await self._safe_agent_call(
            "Guidance",
            self.guidance.generate(text, classification),
        )
        
        complaint = await self._safe_agent_call(
            "Complaint",
            self.complaint.draft(text, classification, user_details),
        )
        
        alert = await self._safe_agent_call(
            "Alert",
            self.alert.generate(text, classification, case_id, language, user_details),
        )
        
        return guidance, complaint, alert

    async def _safe_agent_call(self, agent_name: str, coroutine):
        """Wrap an agent call so that failure doesn't crash the whole pipeline."""
        try:
            return await coroutine
        except Exception as e:
            logger.error(f"{agent_name} agent failed: {e}", exc_info=True)
            return None

    async def _log_case(self, case_id, text, language, classification, response,
                        guidance, complaint, authority_alert):
        """Log case to audit store. Never let logging failures break the response."""
        try:
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            store = get_store()
            store.log_case(
                case_id=case_id,
                input_text=text,
                language=language,
                label=classification.label,
                scam_type=classification.scam_type,
                confidence=classification.confidence,
                reasons=classification.reasons,
                signals=classification.signals,
                model_used=model_name,
                full_response=response.model_dump(),
                guidance_json=guidance.model_dump_json() if guidance else None,
                complaint_json=complaint.model_dump_json() if complaint else None,
                alert_json=authority_alert.model_dump_json() if authority_alert else None,
            )
        except Exception as e:
            logger.error(f"Failed to log case {case_id} to audit store: {e}")

    def _build_reply(
        self,
        language: str,
        classification: ClassificationResult,
        guidance: Optional[GuidanceResult],
    ) -> str:
        """Build the user-facing reply text."""

        if classification.label == "SAFE":
            return self._safe_reply(language, classification)
        elif classification.label == "UNCERTAIN":
            return self._uncertain_reply(language, classification, guidance)
        else:  # SCAM
            return self._scam_reply(language, classification, guidance)

    def _safe_reply(self, language: str, classification: ClassificationResult) -> str:
        """Brief reassurance for SAFE messages."""
        replies = {
            "en": (
                f"✅ This message appears to be legitimate.\n\n"
                f"{classification.reasons}\n\n"
                f"Stay alert: Never share your OTP, PIN, or bank credentials with anyone, "
                f"even if they claim to be from your bank or a government agency."
            ),
            "hi": (
                f"✅ यह संदेश वैध प्रतीत होता है।\n\n"
                f"{classification.reasons}\n\n"
                f"सतर्क रहें: अपना OTP, PIN या बैंक विवरण किसी के साथ साझा न करें, "
                f"भले ही वे बैंक या सरकारी एजेंसी से होने का दावा करें।"
            ),
            "te": (
                f"✅ ఈ సందేశం చట్టబద్ధంగా కనిపిస్తోంది।\n\n"
                f"{classification.reasons}\n\n"
                f"జాగ్రత్తగా ఉండండి: మీ OTP, PIN లేదా బ్యాంక్ వివరాలను ఎవరితోనూ పంచుకోకండి."
            ),
            "kn": (
                f"✅ ಈ ಸಂದೇಶವು ಕಾನೂನುಬದ್ಧವಾಗಿ ಕಾಣುತ್ತದೆ.\n\n"
                f"{classification.reasons}\n\n"
                f"ಎಚ್ಚರವಾಗಿರಿ: ನಿಮ್ಮ OTP, PIN ಅಥವಾ ಬ್ಯಾಂಕ್ ವಿವರಗಳನ್ನು ಯಾರೊಂದಿಗೂ ಹಂಚಿಕೊಳ್ಳಬೇಡಿ."
            ),
        }
        return replies.get(language, replies["en"])

    def _uncertain_reply(
        self, language: str, classification: ClassificationResult,
        guidance: Optional[GuidanceResult]
    ) -> str:
        """Warning + verification guidance for UNCERTAIN."""
        guidance_text = ""
        if guidance:
            steps = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(guidance.steps))
            guidance_text = f"\n\n{guidance.headline}\n\n{guidance.immediate_action}\n\nSteps:\n{steps}"

        replies = {
            "en": (
                f"⚠️ This message shows some warning signs and needs verification.\n\n"
                f"{classification.reasons}"
                f"{guidance_text}\n\n"
                f"🔑 Key: Do NOT pay, share OTP/Aadhaar/bank details, or act under pressure. "
                f"Verify through official channels. If in doubt, call 1930."
            ),
            "hi": (
                f"⚠️ इस संदेश में कुछ चेतावनी के संकेत हैं और सत्यापन की जरूरत है।\n\n"
                f"{classification.reasons}"
                f"{guidance_text}\n\n"
                f"🔑 महत्वपूर्ण: भुगतान न करें, OTP/आधार/बैंक विवरण साझा न करें, "
                f"दबाव में कार्य न करें। आधिकारिक चैनलों से सत्यापित करें। संदेह होने पर 1930 पर कॉल करें।"
            ),
            "te": (
                f"⚠️ ఈ సందేశంలో కొన్ని హెచ్చరిక సంకేతాలు ఉన్నాయి.\n\n"
                f"{classification.reasons}"
                f"{guidance_text}\n\n"
                f"🔑 ముఖ్యం: చెల్లించకండి, OTP/ఆధార్/బ్యాంక్ వివరాలు పంచుకోకండి. 1930కి కాల్ చేయండి."
            ),
            "kn": (
                f"⚠️ ಈ ಸಂದೇಶದಲ್ಲಿ ಕೆಲವು ಎಚ್ಚರಿಕೆ ಚಿಹ್ನೆಗಳಿವೆ.\n\n"
                f"{classification.reasons}"
                f"{guidance_text}\n\n"
                f"🔑 ಪ್ರಮುಖ: ಪಾವತಿಸಬೇಡಿ, OTP/ಆಧಾರ್/ಬ್ಯಾಂಕ್ ವಿವರ ಹಂಚಬೇಡಿ. 1930ಗೆ ಕರೆ ಮಾಡಿ."
            ),
        }
        return replies.get(language, replies["en"])

    def _scam_reply(
        self, language: str, classification: ClassificationResult,
        guidance: Optional[GuidanceResult]
    ) -> str:
        """Full scam warning with guidance."""
        guidance_text = ""
        if guidance:
            steps = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(guidance.steps))
            facts = "\n".join(f"  • {f}" for f in guidance.key_facts)
            guidance_text = (
                f"\n\n{guidance.headline}\n\n"
                f"🚨 {guidance.immediate_action}\n\n"
                f"Steps to take:\n{steps}\n\n"
                f"Key facts:\n{facts}"
            )

        scam_type_display = (classification.scam_type or "fraud").replace("_", " ").title()

        replies = {
            "en": (
                f"🚫 SCAM DETECTED — {scam_type_display}\n\n"
                f"{classification.reasons}"
                f"{guidance_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔴 DO NOT PAY. DO NOT SHARE OTP/AADHAAR/BANK DETAILS. CALL 1930 NOW.\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            "hi": (
                f"🚫 धोखाधड़ी का पता चला — {scam_type_display}\n\n"
                f"{classification.reasons}"
                f"{guidance_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔴 भुगतान न करें। OTP/आधार/बैंक विवरण साझा न करें। अभी 1930 पर कॉल करें।\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            "te": (
                f"🚫 మోసం గుర్తించబడింది — {scam_type_display}\n\n"
                f"{classification.reasons}"
                f"{guidance_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔴 చెల్లించకండి. OTP/ఆధార్/బ్యాంక్ వివరాలు పంచుకోకండి. 1930కి కాల్ చేయండి.\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            "kn": (
                f"🚫 ವಂಚನೆ ಪತ್ತೆಯಾಗಿದೆ — {scam_type_display}\n\n"
                f"{classification.reasons}"
                f"{guidance_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔴 ಪಾವತಿಸಬೇಡಿ. OTP/ಆಧಾರ್/ಬ್ಯಾಂಕ್ ವಿವರ ಹಂಚಬೇಡಿ. 1930ಗೆ ಕರೆ ಮಾಡಿ.\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
        }
        return replies.get(language, replies["en"])
