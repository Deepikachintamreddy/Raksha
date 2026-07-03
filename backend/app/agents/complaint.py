# Raksha — Complaint Drafter Agent
# Produces a factual complaint draft for cybercrime.gov.in / 1930.

from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional

from ..schemas import ComplaintDraft, ClassificationResult, UserDetails
from ..llm.wrapper import get_llm

logger = logging.getLogger("raksha.agents.complaint")

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "complaint.txt"


class ComplaintAgent:
    """Drafts a cyber-crime complaint based on the scam classification."""

    def __init__(self):
        self.system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def draft(
        self,
        original_text: str,
        classification: ClassificationResult,
        user_details: Optional[UserDetails] = None,
    ) -> ComplaintDraft:
        """Generate a complaint draft for a SCAM classification."""
        details_str = ""
        if user_details:
            parts = []
            if user_details.amount_lost:
                parts.append(f"Amount lost: {user_details.amount_lost}")
            if user_details.datetime:
                parts.append(f"Date/time: {user_details.datetime}")
            if user_details.suspect_phone:
                parts.append(f"Suspect phone: {user_details.suspect_phone}")
            if user_details.suspect_upi:
                parts.append(f"Suspect UPI/Account: {user_details.suspect_upi}")
            if user_details.platform:
                parts.append(f"Platform: {user_details.platform}")
            if parts:
                details_str = "\n\nCitizen-provided details:\n" + "\n".join(f"- {p}" for p in parts)

        user_message = (
            f"Classification result:\n"
            f"- Scam type: {classification.scam_type or 'unknown'}\n"
            f"- Signals: {', '.join(classification.signals)}\n\n"
            f"Original suspicious message/transcript:\n{original_text}"
            f"{details_str}"
        )

        llm = get_llm()
        result = await llm.generate_structured(
            system_prompt=self.system_prompt,
            user_message=user_message,
            response_model=ComplaintDraft,
            temperature=0.3,
        )

        logger.info(f"Complaint drafted: category='{result.category}'")
        return result
