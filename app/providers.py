"""Model backends. One job: prompt in, a validated DraftSet out.

Both providers use native structured outputs, so a malformed reply is the API's
problem rather than something we regex our way out of. Swap with LLM_PROVIDER.
"""
from __future__ import annotations

import logging
from typing import Protocol

from app.config import config
from app.models import DraftSet

log = logging.getLogger(__name__)


class Provider(Protocol):
    name: str

    async def complete(self, prompt: str) -> DraftSet: ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic()

    async def complete(self, prompt: str) -> DraftSet:
        response = await self._client.messages.parse(
            model=config.ANTHROPIC_MODEL,
            max_tokens=8000,
            output_config={"effort": config.ANTHROPIC_EFFORT},
            messages=[{"role": "user", "content": prompt}],
            output_format=DraftSet,
        )
        if response.stop_reason == "refusal":
            raise RuntimeError(f"model declined to draft: {response.stop_details}")
        if response.parsed_output is None:
            raise RuntimeError(f"no parseable output (stop_reason: {response.stop_reason})")
        return response.parsed_output


class GeminiProvider:
    name = "gemini"

    def __init__(self) -> None:
        from google import genai

        self._genai = genai
        self._client = genai.Client(api_key=config.gemini_key())

    async def complete(self, prompt: str) -> DraftSet:
        from google.genai import types

        candidate_models = [config.GEMINI_MODEL]
        for fallback in ("gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"):
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_err: Exception | None = None
        for model_name in candidate_models:
            try:
                response = await self._client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=DraftSet,
                    ),
                )
                break
            except Exception as exc:
                last_err = exc
                err_str = str(exc).lower()
                if "503" in err_str or "unavailable" in err_str or "high demand" in err_str:
                    log.warning("Model %s hit temporary 503/high demand, trying fallback...", model_name)
                    continue
                raise
        else:
            raise last_err or RuntimeError("All Gemini models failed")

        # A blocked prompt comes back as a normal response with no candidates,
        # so this has to be checked before reading anything off it.
        feedback = getattr(response, "prompt_feedback", None)
        if feedback and getattr(feedback, "block_reason", None):
            raise RuntimeError(f"Gemini blocked the prompt: {feedback.block_reason}")

        candidates = response.candidates or []
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        finish = getattr(candidates[0], "finish_reason", None)
        if finish and str(finish).rsplit(".", 1)[-1] not in {"STOP", "FINISH_REASON_UNSPECIFIED"}:
            raise RuntimeError(f"Gemini stopped early: {finish}")

        parsed = response.parsed
        if parsed is None:
            raise RuntimeError("Gemini returned no parseable output")
        if isinstance(parsed, DraftSet):
            return parsed
        # Older SDK builds hand back a dict rather than the model instance.
        return DraftSet.model_validate(parsed)


PROVIDERS = {"anthropic": AnthropicProvider, "gemini": GeminiProvider}

_provider: Provider | None = None


def provider() -> Provider:
    """The configured backend, built once and reused."""
    global _provider
    if _provider is None:
        try:
            factory = PROVIDERS[config.LLM_PROVIDER]
        except KeyError:
            raise RuntimeError(
                f"LLM_PROVIDER={config.LLM_PROVIDER!r} is not one of {sorted(PROVIDERS)}"
            ) from None
        _provider = factory()
        log.info("drafting with %s (%s)", _provider.name, config.model_id())
    return _provider


def reset() -> None:
    """Drop the cached backend. Tests and config reloads only."""
    global _provider
    _provider = None
