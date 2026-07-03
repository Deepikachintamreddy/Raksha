# Raksha — Guidance Agent
# Provides calm, empowering advice to the citizen.

from __future__ import annotations
import logging
from pathlib import Path

from ..schemas import GuidanceResult, ClassificationResult
from ..llm.wrapper import get_llm

logger = logging.getLogger("raksha.agents.guidance")

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "guidance.txt"


class GuidanceAgent:
    """Generates step-by-step guidance based on classification result."""

    def __init__(self):
        self.system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def generate(
        self,
        original_text: str,
        classification: ClassificationResult,
    ) -> GuidanceResult:
        """Generate guidance for a SCAM or UNCERTAIN classification."""
        user_message = (
            f"Classification result:\n"
            f"- Label: {classification.label}\n"
            f"- Scam type: {classification.scam_type or 'unknown'}\n"
            f"- Confidence: {classification.confidence}\n"
            f"- Signals: {', '.join(classification.signals)}\n"
            f"- Reasons: {classification.reasons}\n\n"
            f"Original message the citizen received:\n{original_text}"
        )

        llm = get_llm()
        result = await llm.generate_structured(
            system_prompt=self.system_prompt,
            user_message=user_message,
            response_model=GuidanceResult,
            temperature=0.3,
        )

        logger.info(f"Guidance generated: headline='{result.headline[:60]}...'")
        return result
