# Raksha — Provider-Agnostic LLM Wrapper
# Default: Google Gemini via google-genai SDK
# Handles JSON extraction, Pydantic validation, retry with exponential backoff,
# rate-limit handling, and input sanitization.

from __future__ import annotations
import json
import re
import os
import logging
import asyncio
import time
from typing import Type, TypeVar, Optional

from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

# Load .env from the backend directory specifically
from pathlib import Path
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

logger = logging.getLogger("raksha.llm")

T = TypeVar("T", bound=BaseModel)

# ── Input validation ──
MAX_INPUT_LENGTH = 10000  # Characters — prevents abuse and token-bomb attacks
MIN_INPUT_LENGTH = 5      # Minimum meaningful input


def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent injection and abuse."""
    if not text or not text.strip():
        raise ValueError("Input text cannot be empty")

    text = text.strip()

    if len(text) > MAX_INPUT_LENGTH:
        logger.warning(f"Input truncated from {len(text)} to {MAX_INPUT_LENGTH} chars")
        text = text[:MAX_INPUT_LENGTH]

    if len(text) < MIN_INPUT_LENGTH:
        raise ValueError(f"Input too short (min {MIN_INPUT_LENGTH} characters)")

    # Strip null bytes and control characters (keep newlines and tabs)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    return text


def _extract_json(text: str) -> str:
    """Extract JSON from LLM output that may be wrapped in markdown code fences."""
    # Try to find JSON in code fences first
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # Try to find a JSON object or array
    obj_match = re.search(r"(\{.*\})", text, re.DOTALL)
    if obj_match:
        return obj_match.group(1).strip()

    arr_match = re.search(r"(\[.*\])", text, re.DOTALL)
    if arr_match:
        return arr_match.group(1).strip()

    return text.strip()


class LLMWrapper:
    """Provider-agnostic LLM wrapper with retry, rate-limit handling, and timeout."""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.provider = os.getenv("LLM_PROVIDER", "gemini")
        self._client = None
        self._request_count = 0
        self._last_request_time = 0.0
        self._cache_file = Path(__file__).parent.parent.parent / "data" / "llm_cache.json"
        self._load_cache()

        if not self.api_key or self.api_key == "your-gemini-api-key-here":
            logger.warning(
                "⚠️  GEMINI_API_KEY is not set or is a placeholder! "
                "Add your real key to backend/.env"
            )

    def _load_cache(self):
        try:
            if self._cache_file.exists():
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                logger.info(f"Loaded {len(self._cache)} items from disk cache at {self._cache_file}")
            else:
                self._cache = {}
        except Exception as e:
            logger.warning(f"Failed to load disk cache: {e}")
            self._cache = {}

    def _save_cache(self):
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save disk cache: {e}")

    def _get_client(self):
        if self._client is None:
            if self.provider == "gemini":
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            else:
                raise ValueError(f"Unsupported LLM provider: {self.provider}")
        return self._client

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        timeout_seconds: int = 60,
    ) -> str:
        """Generate raw text from the LLM with retry and rate-limit handling."""
        import hashlib
        cache_key = hashlib.sha256(
            f"raw:{system_prompt}:{user_message}:{temperature}:{max_tokens}".encode("utf-8")
        ).hexdigest()

        if cache_key in self._cache:
            logger.info(f"Retrieving raw response from cache (HIT)")
            return self._cache[cache_key]

        if self.provider == "gemini":
            result = await self._generate_gemini(
                system_prompt, user_message, temperature, max_tokens, timeout_seconds
            )
            self._cache[cache_key] = result
            self._save_cache()
            return result
        raise ValueError(f"Unsupported provider: {self.provider}")

    async def _generate_gemini(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
        timeout_seconds: int,
    ) -> str:
        """Generate using Google Gemini with retry + exponential backoff."""
        from google import genai
        from google.genai import types

        client = self._get_client()

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                # Rate limiting: minimum 200ms between requests
                now = time.monotonic()
                elapsed = now - self._last_request_time
                if elapsed < 0.2:
                    await asyncio.sleep(0.2 - elapsed)

                def _sync_generate():
                    response = client.models.generate_content(
                        model=self.model_name,
                        contents=user_message,
                        config=config,
                    )
                    return response.text

                self._last_request_time = time.monotonic()
                self._request_count += 1

                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, _sync_generate),
                    timeout=timeout_seconds,
                )

                if result is None:
                    raise ValueError("LLM returned None — possible content filter block")

                return result

            except asyncio.TimeoutError:
                last_error = TimeoutError(
                    f"LLM request timed out after {timeout_seconds}s"
                )
                logger.warning(f"LLM timeout (attempt {attempt + 1}/{max_retries})")

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Rate limit — back off exponentially
                if "429" in error_str or "rate" in error_str or "quota" in error_str:
                    backoff = 2 ** attempt * 2  # 2s, 4s, 8s
                    logger.warning(
                        f"Rate limited (attempt {attempt + 1}), backing off {backoff}s"
                    )
                    await asyncio.sleep(backoff)
                    continue

                # Auth error — no point retrying
                if "401" in error_str or "403" in error_str or "api_key" in error_str:
                    logger.error(f"Authentication error: {e}")
                    raise ValueError(
                        "Gemini API authentication failed. Check your GEMINI_API_KEY in backend/.env"
                    ) from e

                # Other error — retry with backoff
                logger.warning(
                    f"LLM error (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))

        raise ValueError(
            f"LLM failed after {max_retries} attempts. Last error: {last_error}"
        )

    async def generate_structured(
        self,
        system_prompt: str,
        user_message: str,
        response_model: Type[T],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> T:
        """
        Generate and parse into a Pydantic model.
        Retries up to 3 times if the LLM produces malformed JSON.
        """
        import hashlib
        cache_key = hashlib.sha256(
            f"{system_prompt}:{user_message}:{response_model.__name__}".encode("utf-8")
        ).hexdigest()

        if cache_key in self._cache:
            logger.info(f"Retrieving structure response from cache (HIT)")
            return response_model.model_validate_json(self._cache[cache_key])

        last_error = None
        current_message = user_message

        for attempt in range(3):  # max 3 attempts
            try:
                raw = await self.generate(
                    system_prompt, current_message, temperature, max_tokens
                )
                logger.debug(f"LLM raw output (attempt {attempt + 1}): {raw[:500]}")

                json_str = _extract_json(raw)
                data = json.loads(json_str)
                validated = response_model.model_validate(data)

                # Save validated JSON string to cache
                self._cache[cache_key] = validated.model_dump_json()
                if len(self._cache) > 1000:
                    first_key = next(iter(self._cache))
                    self._cache.pop(first_key)
                self._save_cache()

                return validated

            except (json.JSONDecodeError, ValidationError) as e:
                last_error = e
                logger.warning(
                    f"LLM output parsing failed (attempt {attempt + 1}): {e}"
                )

                if attempt < 2:
                    # Retry with increasingly explicit instructions
                    current_message = (
                        f"{user_message}\n\n"
                        f"CRITICAL: Your previous response was NOT valid JSON. "
                        f"Return ONLY a raw JSON object (no markdown, no code fences, "
                        f"no extra text before or after). The JSON must match this schema:\n"
                        f"{json.dumps(response_model.model_json_schema(), indent=2)}"
                    )

        raise ValueError(
            f"Failed to parse LLM output after 3 attempts. Last error: {last_error}"
        )

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        mime_type: str,
    ) -> str:
        """Transcribe audio bytes using Gemini multimodal model."""
        from google.genai import types
        client = self._get_client()

        # Construct Part containing the inline data
        audio_part = types.Part.from_bytes(
            data=audio_bytes,
            mime_type=mime_type,
        )

        def _sync_transcribe():
            response = client.models.generate_content(
                model=self.model_name,
                contents=[
                    audio_part,
                    "Provide a highly accurate transcription of the spoken audio. Output only the transcript text."
                ]
            )
            return response.text

        try:
            result = await asyncio.get_event_loop().run_in_executor(None, _sync_transcribe)
            if not result:
                return ""
            return result.strip()
        except Exception as e:
            logger.error(f"Audio transcription failed: {e}")
            raise ValueError(f"Transcription failed: {e}")


# Singleton instance
_wrapper: Optional[LLMWrapper] = None


def get_llm() -> LLMWrapper:
    """Get the singleton LLM wrapper instance."""
    global _wrapper
    if _wrapper is None:
        _wrapper = LLMWrapper()
    return _wrapper
