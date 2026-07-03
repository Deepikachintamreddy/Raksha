# Raksha — Authority Alert Generator Agent
# Produces structured alert artifact for MHA/I4C/telecom abuse desk.

from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional
from uuid import uuid4
from datetime import datetime

from ..schemas import AuthorityAlert, ClassificationResult, UserDetails
from ..llm.wrapper import get_llm

logger = logging.getLogger("raksha.agents.alert")

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "alert.txt"


class AlertAgent:
    """Generates authority alert artifacts for confirmed SCAM cases."""

    def __init__(self):
        self.system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def generate(
        self,
        original_text: str,
        classification: ClassificationResult,
        case_id: str,
        language: str = "en",
        user_details: Optional[UserDetails] = None,
    ) -> AuthorityAlert:
        """Generate an authority alert for a SCAM case."""
        details_str = ""
        if user_details:
            parts = []
            if user_details.suspect_phone:
                parts.append(f"Suspect phone: {user_details.suspect_phone}")
            if user_details.suspect_upi:
                parts.append(f"Suspect UPI/Account: {user_details.suspect_upi}")
            if user_details.platform:
                parts.append(f"Platform: {user_details.platform}")
            if user_details.amount_lost:
                parts.append(f"Amount lost: {user_details.amount_lost}")
            if parts:
                details_str = "\nCase metadata:\n" + "\n".join(f"- {p}" for p in parts)

        user_message = (
            f"Classifier output:\n"
            f"- Scam type: {classification.scam_type or 'unknown'}\n"
            f"- Confidence: {classification.confidence}\n"
            f"- Signals: {', '.join(classification.signals)}\n"
            f"- Language: {language}\n"
            f"- Case/audit ref: {case_id}\n"
            f"{details_str}\n\n"
            f"Original message:\n{original_text}"
        )

        llm = get_llm()
        result = await llm.generate_structured(
            system_prompt=self.system_prompt,
            user_message=user_message,
            response_model=AuthorityAlert,
            temperature=0.2,
        )

        # Ensure audit_ref is set
        result.audit_ref = case_id

        logger.info(f"Authority alert generated: alert_id={result.alert_id}")
        return result
