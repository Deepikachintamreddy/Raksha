# Raksha — Scam Classifier Agent
# Core agent tuned for LOW FALSE POSITIVES.
# SCAM requires confidence >= 0.80 AND 2+ converging signals.
# Double-enforced: both in the prompt AND in code.

from __future__ import annotations
import logging
from pathlib import Path

from ..schemas import ClassificationResult
from ..llm.wrapper import get_llm

logger = logging.getLogger("raksha.agents.classifier")

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "classifier.txt"

# ── FPR Guardrails (non-negotiable, match BUILD_PLAN rules) ──
MIN_SCAM_CONFIDENCE = 0.80
MIN_SCAM_SIGNALS = 2

# Valid scam types from the prompt spec
VALID_SCAM_TYPES = {
    "digital_arrest", "courier_parcel", "kyc_bank",
    "loan_app", "lottery_prize", "investment_job", "other_fraud",
}


class ClassifierAgent:
    """Classifies a suspicious message as SCAM / SAFE / UNCERTAIN."""

    def __init__(self):
        if not PROMPT_PATH.exists():
            raise FileNotFoundError(
                f"Classifier prompt file not found: {PROMPT_PATH}. "
                f"Ensure prompts/ directory is properly set up."
            )
        self.system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def classify(self, text: str) -> ClassificationResult:
        """
        Classify the given text.
        Returns a ClassificationResult with label, scam_type, confidence, signals, reasons.
        """
        llm = get_llm()
        result = await llm.generate_structured(
            system_prompt=self.system_prompt,
            user_message=text,
            response_model=ClassificationResult,
            temperature=0.2,  # Low temperature for consistent classification
        )

        # ── Post-LLM Guardrails (enforced in code, not just in the prompt) ──

        # Rule 1: SCAM needs confidence >= 0.80 AND 2+ signals
        if result.label == "SCAM":
            if result.confidence < MIN_SCAM_CONFIDENCE or len(result.signals) < MIN_SCAM_SIGNALS:
                logger.warning(
                    f"Classifier returned SCAM but confidence={result.confidence:.2f}, "
                    f"signals={len(result.signals)}. DOWNGRADING to UNCERTAIN. "
                    f"(Rule: need >={MIN_SCAM_CONFIDENCE} confidence AND >={MIN_SCAM_SIGNALS} signals)"
                )
                result.label = "UNCERTAIN"

        # Rule 2: Normalize scam_type to known values
        if result.scam_type and result.scam_type not in VALID_SCAM_TYPES:
            normalized = result.scam_type.lower().strip().replace(" ", "_").replace("-", "_")
            if normalized in VALID_SCAM_TYPES:
                result.scam_type = normalized
            else:
                logger.warning(
                    f"Unknown scam_type '{result.scam_type}', mapping to 'other_fraud'"
                )
                result.scam_type = "other_fraud"

        # Rule 3: SAFE should not have a scam_type
        if result.label == "SAFE":
            result.scam_type = None

        # Rule 4: Clamp confidence to valid range (defensive)
        result.confidence = max(0.0, min(1.0, result.confidence))

        logger.info(
            f"Classification: {result.label} | type={result.scam_type} | "
            f"confidence={result.confidence:.2f} | signals={len(result.signals)}"
        )
        return result
