"""
AI LLM gateway for the sponsor research pipeline.
Single interface for all AI LLM calls.
Supports anthropic, openai, and google as backends via LLM_PROVIDER in .env
The rest of the pipeline goes through LLMClient class. No other llm provider is imported afterward.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from sponsor_pipeline.config import Settings
from sponsor_pipeline.logger import get_logger

logger = get_logger(__name__)


# Abstract backend interface
class _LLMBackend(ABC):
    """
    Internal interface all provider backends must implement.
    """

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """
        Send a prompt and return the model's text response.
        """


# For Anthropic / Claude backend -----------------------------
class _AnthropicBackend(_LLMBackend):
    def __init__(self, api_key: str, model: str) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, system: str, user: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text or ""


# For OpenAI / ChatGPT backend -------------------------------
class _OpenAIBackend(_LLMBackend):
    def __init__(self, api_key: str, model: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def complete(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""


# For Google / Gemini backend --------------------------------
# Uses the new google.genai SDK (google-genai package) — the same one
# already used in services/sponsor_evaluator/llm/sponsor_dimension_evaluator.py.
# The old google.generativeai package is deprecated and is not installed
# (see requirements.txt), so importing it here used to raise ModuleNotFoundError
# for every LLM_PROVIDER=google call that went through LLMClient (discover,
# research, contacts stages).
class _GoogleBackend(_LLMBackend):
    def __init__(self, api_key: str, model: str) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model

    def complete(self, system: str, user: str) -> str:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._model,
            contents=user,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        return response.text or ""


# ------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a sponsor research assistant for Hack Canada, a student hackathon with a strong Waterloo and Canadian audience. "
    "Be realistic about sponsorship fit, not company fame."
)


class LLMClient:
    """
    AI LLM Client instantiated by PipelineOrchestrator and passed to all services that need an AI LLM access.
    LLM provider is selected via LLM_PROVIDER in .env
    """

    def __init__(self, settings: Settings) -> None:
        provider = settings.llm_provider
        model = settings.llm_model
        logger.info("Initializing LLM client: provider=%s, model=%s", provider, model)
        self._provider = provider

        if provider == "anthropic":
            if not settings.anthropic_api_key:
                raise ValueError(
                    "You need to set ANTHROPIC_API_KEY in .env file for this LLM provider."
                )
            self._backend = _AnthropicBackend(settings.anthropic_api_key, model)

        elif provider == "openai":
            if not settings.openai_api_key:
                raise ValueError(
                    "You need to set OPENAI_API_KEY in .env file for this LLM provider."
                )
            self._backend = _OpenAIBackend(settings.openai_api_key, model)

        elif provider == "google":
            if not settings.google_api_key:
                raise ValueError(
                    "You need to set GOOGLE_API_KEY in .env file for this LLM provider."
                )
            self._backend = _GoogleBackend(settings.google_api_key, model)

        else:
            raise ValueError(
                f"Unsupported LLM provider: '{provider}'. Choose one of 'anthropic', 'openai', 'google'."
            )

    def complete(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """
        Send a prompt and return the model's text response.
        """
        logger.info("Sending LLM completion request")
        user_content = prompt
        if context:
            user_content += "\n\nContext:\n" + json.dumps(
                context, indent=2, default=str
            )
            # Added the try  block to provide a user firendly error 
        try:
            response = self._backend.complete(_SYSTEM_PROMPT, user_content)
        except Exception as exc:
            # Try to detect authentication-like failures and raise a friendly error
            msg = str(exc) or ""
            low = msg.lower()
            if "401" in msg or "incorrect api key" in low or "invalid_api_key" in low or "authentication" in low:
                env_name = {
                    "anthropic": "ANTHROPIC_API_KEY",
                    "openai": "OPENAI_API_KEY",
                    "google": "GOOGLE_API_KEY",
                }.get(self._provider, "API key")
                raise ValueError(
                    f"LLM authentication failed for provider '{self._provider}'."
                    f" Check {env_name} in your .env and ensure it is a valid key."
                ) from exc
            raise
        logger.info("Received LLM completion response")
        return response

    def complete_structured(self, prompt: str, schema_hint: str) -> dict[str, Any]:
        """
        Send a prompt and parse the response as JSON.
        """
        full_prompt = (
            f"{prompt}\n\n"
            f"Return ONLY valid JSON matching this shape:\n{schema_hint}\n"
            "Do not include markdown fences."
        )
        text = self.complete(full_prompt)
        parsed = _parse_json(text)
        logger.debug(
            "Parsed structured LLM response with keys: %s", list(parsed.keys())
        )
        return parsed


def _parse_json(text: str) -> dict[str, Any]:
    """
    Strip markdown fences if present and parse JSON.
    """
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)
