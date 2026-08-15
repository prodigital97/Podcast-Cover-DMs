"""The model backends, and the failure paths that would otherwise send a bad draft."""
import types as pytypes

import pytest

from app import providers
from app.config import config
from app.models import DraftSet
from tests.fakes import draft_set


@pytest.fixture(autouse=True)
def reset_provider():
    providers.reset()
    yield
    providers.reset()


def test_an_unknown_provider_fails_loudly(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai")
    with pytest.raises(RuntimeError, match="not one of"):
        providers.provider()


def test_the_backend_is_built_once_and_reused(monkeypatch):
    built = []

    class Counting:
        name = "counting"

        def __init__(self):
            built.append(1)

    monkeypatch.setitem(providers.PROVIDERS, "counting", Counting)
    monkeypatch.setattr(config, "LLM_PROVIDER", "counting")
    providers.provider()
    providers.provider()
    assert len(built) == 1


def test_model_id_follows_the_selected_provider(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_MODEL", "gemini-x-flash")
    assert config.model_id() == "gemini-x-flash"
    monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
    assert config.model_id() == config.ANTHROPIC_MODEL


# --- Gemini response handling ---------------------------------------------

def gemini_response(*, parsed=None, block_reason=None, finish="STOP", candidates=True):
    candidate = pytypes.SimpleNamespace(finish_reason=finish)
    return pytypes.SimpleNamespace(
        parsed=parsed,
        prompt_feedback=pytypes.SimpleNamespace(block_reason=block_reason),
        candidates=[candidate] if candidates else [],
    )


async def run_gemini(response):
    """Drive GeminiProvider.complete against a canned response, no network."""
    provider = providers.GeminiProvider.__new__(providers.GeminiProvider)

    async def generate_content(**kwargs):
        return response

    provider._client = pytypes.SimpleNamespace(
        aio=pytypes.SimpleNamespace(models=pytypes.SimpleNamespace(
            generate_content=generate_content))
    )
    return await provider.complete("prompt")


def test_gemini_returns_the_parsed_draft_set():
    import asyncio

    expected = draft_set()
    assert asyncio.run(run_gemini(gemini_response(parsed=expected))) == expected


def test_gemini_accepts_a_dict_from_older_sdk_builds():
    import asyncio

    result = asyncio.run(run_gemini(gemini_response(parsed=draft_set().model_dump())))
    assert isinstance(result, DraftSet)
    assert result.drafts[0].tone == "warm"


@pytest.mark.parametrize(
    "response, message",
    [
        (gemini_response(block_reason="SAFETY"), "blocked the prompt"),
        (gemini_response(candidates=False), "no candidates"),
        (gemini_response(finish="MAX_TOKENS"), "stopped early"),
        (gemini_response(parsed=None), "no parseable output"),
    ],
)
def test_gemini_failures_raise_instead_of_returning_a_half_draft(response, message):
    import asyncio

    with pytest.raises(RuntimeError, match=message):
        asyncio.run(run_gemini(response))


def test_the_response_schema_survives_conversion_to_geminis_dialect():
    from google.genai import _transformers

    schema = _transformers.t_schema(None, DraftSet).model_dump(exclude_none=True)
    assert schema["properties"]["stage"]["enum"][0] == "first_contact"
    # The nullable pipeline fields are what a strict schema dialect tends to drop.
    assert schema["properties"]["lead_update"]["properties"]["needs"]["nullable"] is True
