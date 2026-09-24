from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from openai import AsyncOpenAI
from openai.resources.chat.completions import AsyncCompletions
from openai.types.chat import ChatCompletion
from pydantic import BaseModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from v2.adapters.models import (
    ProviderStructuredModel,
    ReasoningContentFallbackClient,
    _promote_reasoning_content,
    _ReasoningContentCompletions,
)
from v2.runtime import RequestEnvelope


class _Ping(BaseModel):
    answer: str


def _reasoning_first_completion(
    *,
    content: Any,
    reasoning_content: Any,
    model: str = "test-model/reasoning-flash",
) -> ChatCompletion:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if reasoning_content is not None:
        message["reasoning_content"] = reasoning_content
    return ChatCompletion.model_validate(
        {
            "id": "chatcmpl-test",
            "created": 1700000000,
            "model": model,
            "object": "chat.completion",
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": message,
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }
    )


def _shaped_body(*, content: Any, reasoning_content: Any, model: str) -> dict[str, Any]:
    return _reasoning_first_completion(
        content=content, reasoning_content=reasoning_content, model=model
    ).model_dump(mode="json")


def test_promote_moves_reasoning_content_to_empty_content():
    response = _reasoning_first_completion(
        content="", reasoning_content='{"answer":"hi"}'
    )
    result = _promote_reasoning_content(response)
    assert result.choices[0].message.content == '{"answer":"hi"}'
    assert getattr(result.choices[0].message, "reasoning_content") == '{"answer":"hi"}'


def test_promote_leaves_populated_content_alone():
    response = _reasoning_first_completion(
        content="real", reasoning_content='{"answer":"other"}'
    )
    result = _promote_reasoning_content(response)
    assert result.choices[0].message.content == "real"


def test_promote_handles_missing_reasoning_content():
    response = _reasoning_first_completion(content="", reasoning_content=None)
    result = _promote_reasoning_content(response)
    assert result.choices[0].message.content == ""


def test_promote_handles_none_content():
    response = _reasoning_first_completion(
        content=None, reasoning_content='{"answer":"hi"}'
    )
    result = _promote_reasoning_content(response)
    assert result.choices[0].message.content == '{"answer":"hi"}'


def test_fallback_is_model_name_agnostic():
    response = _reasoning_first_completion(
        content="",
        reasoning_content='{"answer":"hi"}',
        model="totally-unrelated-model/9.9",
    )
    result = _promote_reasoning_content(response)
    assert result.choices[0].message.content == '{"answer":"hi"}'


def test_no_model_name_branching_in_fallback_code():
    source = (
        Path(__file__).resolve().parents[2] / "adapters" / "models.py"
    ).read_text()
    assert "deepseek" not in source.lower()
    assert "_promote_reasoning_content" in source
    assert "ReasoningContentFallbackClient" in source


@pytest.mark.anyio
async def test_client_create_applies_fallback():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_shaped_body(
                content="",
                reasoning_content='{"answer":"hi"}',
                model="test-model/reasoning-flash",
            ),
        )

    transport = httpx.MockTransport(handler)
    client = ReasoningContentFallbackClient(
        api_key="placeholder",
        http_client=httpx.AsyncClient(transport=transport),
    )
    assert isinstance(client, AsyncOpenAI)
    resp = await client.chat.completions.create(
        model="test-model/reasoning-flash",
        messages=[{"role": "user", "content": "hi"}],
        response_format={"type": "json_object"},
    )
    assert resp.choices[0].message.content == '{"answer":"hi"}'


@pytest.mark.anyio
async def test_client_create_passes_through_non_completion(monkeypatch):
    sentinel = object()

    async def fake_create(self: Any, *args: Any, **kwargs: Any) -> Any:
        return sentinel

    monkeypatch.setattr(AsyncCompletions, "create", fake_create)
    client = ReasoningContentFallbackClient(api_key="placeholder")
    result = await _ReasoningContentCompletions(client).create()
    assert result is sentinel


def _mock_openai_model(
    *, content: Any, reasoning_content: Any, model: str
) -> OpenAIChatModel:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_shaped_body(
                content=content,
                reasoning_content=reasoning_content,
                model=model,
            ),
        )

    transport = httpx.MockTransport(handler)
    mock_client = ReasoningContentFallbackClient(
        api_key="placeholder",
        http_client=httpx.AsyncClient(transport=transport),
    )
    return OpenAIChatModel(
        model, provider=OpenAIProvider(openai_client=mock_client)
    )


@pytest.mark.anyio
async def test_generate_parses_reasoning_content_structured_output(monkeypatch):
    openai_model = _mock_openai_model(
        content="",
        reasoning_content='{"answer":"hi"}',
        model="test-model/reasoning-flash",
    )
    monkeypatch.setattr(
        ProviderStructuredModel, "_models", lambda self: [("nvidia", openai_model)]
    )
    envelope = RequestEnvelope.freeze(
        provider="nvidia",
        model="test-model/reasoning-flash",
        route="intake",
        prompt="p",
        context={},
        tool_schemas={},
        planner_version="v2",
    )
    result = await ProviderStructuredModel(
        "nvidia", "test-model/reasoning-flash"
    ).generate(schema=_Ping, prompt="p", payload={}, envelope=envelope)
    assert isinstance(result, _Ping)
    assert result.answer == "hi"


@pytest.mark.anyio
async def test_generate_still_parses_normal_content(monkeypatch):
    openai_model = _mock_openai_model(
        content='{"answer":"normal"}',
        reasoning_content=None,
        model="test-model/reasoning-flash",
    )
    monkeypatch.setattr(
        ProviderStructuredModel, "_models", lambda self: [("nvidia", openai_model)]
    )
    envelope = RequestEnvelope.freeze(
        provider="nvidia",
        model="test-model/reasoning-flash",
        route="intake",
        prompt="p",
        context={},
        tool_schemas={},
        planner_version="v2",
    )
    result = await ProviderStructuredModel(
        "nvidia", "test-model/reasoning-flash"
    ).generate(schema=_Ping, prompt="p", payload={}, envelope=envelope)
    assert isinstance(result, _Ping)
    assert result.answer == "normal"
