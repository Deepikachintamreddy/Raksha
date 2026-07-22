# -*- coding: utf-8 -*-
# Raksha — Rehearsal Simulator & Debrief Agents

from __future__ import annotations
import re
import json
import logging
from pathlib import Path
from ..schemas import RehearsalScorecard
from ..llm.wrapper import get_llm

logger = logging.getLogger("raksha.agents.simulator")

SIMULATOR_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "simulator.txt"
DEBRIEF_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "debrief.txt"


def sanitize_simulator_output(text: str) -> str:
    """
    Defensive post-LLM sanitization to ensure the simulator NEVER produces
    real-looking contact or payment details under any circumstances.
    """
    # 1. Replace Indian phone numbers (10 digits starting with 6-9, optional +91)
    text = re.sub(r"\b(?:\+91[\-\s]?)?[6789]\d{9}\b", "+91-0000000000", text)

    # 2. Replace UPI IDs (something@bank)
    text = re.sub(r"\b[a-zA-Z0-9\.\-_]+@[a-zA-Z]{3,15}\b", "scammer@placeholder", text)

    # 3. Replace URLs/Links
    # Avoid replacing general punctuation or dots in sentences. Match standard url patterns.
    url_pattern = r"\b(?:https?://)?[a-zA-Z0-9\.\-]+\.[a-zA-Z]{2,6}(?:/[a-zA-Z0-9\.\-\?&\+=\#]*)?\b"
    # Ensure we don't break simple word endings. Check if contains typical domains or slashes.
    def replace_url(match):
        val = match.group(0).lower()
        if any(ext in val for ext in [".com", ".in", ".org", ".net", ".xyz", "http"]):
            return "http://fake-link.com"
        return match.group(0)
    text = re.sub(url_pattern, replace_url, text)

    # 4. Replace Bank Account Numbers (9 to 18 digits)
    # Exclude 1930 and the phone placeholder "+91-0000000000" or "0000000000"
    def replace_acc(match):
        val = match.group(0)
        if val == "1930" or val == "0000000000":
            return val
        return "0000000000"
    text = re.sub(r"\b\d{9,18}\b", replace_acc, text)

    return text


class SimulatorAgent:
    """Roleplays a scammer to train/inoculate citizens."""

    def __init__(self):
        if not SIMULATOR_PROMPT_PATH.exists():
            raise FileNotFoundError(f"Simulator prompt not found at {SIMULATOR_PROMPT_PATH}")
        self.system_prompt = SIMULATOR_PROMPT_PATH.read_text(encoding="utf-8")

    async def generate_reply(self, history: list[dict]) -> str:
        """
        Generate the next response from the simulated scammer.
        history: list of dicts [{"role": "user"|"assistant"|"system", "content": "..."}]
        """
        # Format conversation history for the LLM call
        formatted_history = []
        for msg in history:
            role = msg["role"]
            content = msg["content"]
            formatted_history.append(f"{role.upper()}: {content}")
        
        user_message = "Conversation history:\n" + "\n".join(formatted_history) + "\n\nProvide the next response as the simulated scammer."

        llm = get_llm()
        raw_response = await llm.generate(
            system_prompt=self.system_prompt,
            user_message=user_message,
            temperature=0.7,  # slightly higher temperature for conversational variety
        )

        # Apply safety sanitizer
        sanitized_response = sanitize_simulator_output(raw_response)
        logger.info("Simulator response generated and sanitized.")
        return sanitized_response


class DebriefAgent:
    """Analyzes rehearsal conversation and produces scorecard."""

    def __init__(self):
        if not DEBRIEF_PROMPT_PATH.exists():
            raise FileNotFoundError(f"Debrief prompt not found at {DEBRIEF_PROMPT_PATH}")
        self.system_prompt = DEBRIEF_PROMPT_PATH.read_text(encoding="utf-8")

    async def debrief(self, history: list[dict]) -> RehearsalScorecard:
        """Analyze conversation history and generate a scorecard."""
        # Format transcript
        formatted_transcript = []
        for idx, msg in enumerate(history):
            role = msg["role"]
            content = msg["content"]
            formatted_transcript.append(f"[{idx+1}] {role.upper()}: {content}")
        
        user_message = "Conversation transcript:\n" + "\n".join(formatted_transcript) + "\n\nAnalyze and return the scorecard."

        llm = get_llm()
        scorecard = await llm.generate_structured(
            system_prompt=self.system_prompt,
            user_message=user_message,
            response_model=RehearsalScorecard,
            temperature=0.2,
        )

        logger.info("Debrief scorecard generated.")
        return scorecard
