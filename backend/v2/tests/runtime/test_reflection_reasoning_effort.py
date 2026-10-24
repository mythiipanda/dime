from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from openai.types.chat import ChatCompletion
from pydantic import BaseModel
from pydantic_ai.providers.openai import OpenAIProvider

from v2.adapters.models import (
    DimeOpenAIChatModel,
    ProviderStructuredModel,
    ReasoningContentFallbackClient,
)
from v2.adapters.structured import EndpointCapabilities, OutputStrategy, Support
from v2.runtime import RequestEnvelope


class _Ping(BaseModel):
    answer: str


def _completion_body(
    *,
    content: Any = "{\"answer\":\"ok\"}",
    reasoning_content: Any = None,
    finish_reason: Any = "stop",
    model: str = "Beam-1.0-501B-A23B",
) -> dict[str, Any]:
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
                    "finish_reason": finish_reason,
                    "index": 0,
                    "message": message,
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
    ).model_dump(mode="json")


def _mock_model(
    *,
    captured: list[dict[str, Any]],
    model_name: str = "Beam-1.0-501B-A23B",
    content: Any = "{\"answer\":\"ok\"}",
    endpoint: str = "https://api.reflection.ai/openai/v1",
) -> DimeOpenAIChatModel:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content.decode()))
        return httpx.Response(
            200,
            json=_completion_body(content=content, model=model_name),
        )

    transport = httpx.MockTransport(handler)
    client = ReasoningContentFallbackClient(
        api_key="placeholder",
        http_client=httpx.AsyncClient(transport=transport),
    )
    return DimeOpenAIChatModel(
        model_name,
        provider=OpenAIProvider(openai_client=client),
        capabilities=EndpointCapabilities(
            endpoint=endpoint,
            strict_json_schema=Support.MEASURED,
            tool_calling=Support.MEASURED,
            strict_tool_definitions=Support.MEASURED,
        ),
    )


def _envelope(
    *,
    provider: str = "reflection",
    model: str = "Beam-1.0-501B-A23B",
    route: str = "intake",
) -> RequestEnvelope:
    return RequestEnvelope.freeze(
        provider=provider,
        model=model,
        route=route,
        prompt="p",
        context={},
        tool_schemas={},
        planner_version="v2",
    )


def test_stage_model_settings_unit_isolation():
    for route in ("intake", "synthesizer"):
        assert ProviderStructuredModel._stage_model_settings(
            "reflection", "Beam-1.0-501B-A23B", route
        ) == {"openai_reasoning_effort": "low"}
        assert ProviderStructuredModel._stage_model_settings(
            "reflection", "beam-1", route
        ) == {"openai_reasoning_effort": "low"}

    for other_route in (
        "planner",
        "repair",
        "semantic_verifier",
        "requirement_review",
    ):
        assert ProviderStructuredModel._stage_model_settings(
            "reflection", "Beam-1.0-501B-A23B", other_route
        ) is None

    for other_provider in (
        "gemini",
        "nvidia",
        "groq",
        "mistral",
        "openrouter",
        "inception",
        "cerebras",
        "agnes",
    ):
        for route in ("intake", "synthesizer"):
            assert ProviderStructuredModel._stage_model_settings(
                other_provider, "Beam-1.0-501B-A23B", route
            ) is None
            assert ProviderStructuredModel._stage_model_settings(
                other_provider, "default-model", route
            ) is None

    for route in ("intake", "synthesizer"):
        assert ProviderStructuredModel._stage_model_settings(
            "reflection", "unrelated-model", route
        ) is None


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.parametrize("route", ["intake", "synthesizer"])
async def test_reflection_intake_and_synthesizer_outbound_requests_carry_low_reasoning_effort(
    anyio_backend, route, monkeypatch
):
    assert anyio_backend == "asyncio"
    captured: list[dict[str, Any]] = []
    chat_model = _mock_model(captured=captured, model_name="Beam-1.0-501B-A23B")

    sm = ProviderStructuredModel("reflection", "Beam-1.0-501B-A23B")
    monkeypatch.setattr(sm, "_models", lambda: [("reflection", chat_model)])

    result = await sm.generate(
        schema=_Ping,
        prompt="test prompt",
        payload={"query": "celtics"},
        envelope=_envelope(
            provider="reflection", model="Beam-1.0-501B-A23B", route=route
        ),
    )
    assert isinstance(result, _Ping)
    assert result.answer == "ok"
    assert len(captured) == 1
    req = captured[0]

    assert req.get("reasoning_effort") == "low"
    assert req.get("max_tokens") is None
    assert req.get("max_completion_tokens") is None
    assert sm.last_output_strategy == OutputStrategy.STRICT_SCHEMA
    assert sm.last_failures == []


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.parametrize(
    "route", ["planner", "repair", "semantic_verifier", "requirement_review"]
)
async def test_reflection_other_stages_omit_reasoning_effort(
    anyio_backend, route, monkeypatch
):
    assert anyio_backend == "asyncio"
    captured: list[dict[str, Any]] = []
    chat_model = _mock_model(captured=captured, model_name="Beam-1.0-501B-A23B")

    sm = ProviderStructuredModel("reflection", "Beam-1.0-501B-A23B")
    monkeypatch.setattr(sm, "_models", lambda: [("reflection", chat_model)])

    result = await sm.generate(
        schema=_Ping,
        prompt="test prompt",
        payload={"query": "celtics"},
        envelope=_envelope(
            provider="reflection", model="Beam-1.0-501B-A23B", route=route
        ),
    )
    assert isinstance(result, _Ping)
    assert len(captured) == 1
    assert "reasoning_effort" not in captured[0]
    assert captured[0].get("max_tokens") is None
    assert captured[0].get("max_completion_tokens") is None


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.parametrize("route", ["intake", "synthesizer"])
@pytest.mark.parametrize(
    "provider,model_name",
    [
        ("nvidia", "nvidia/nemotron-3-super-120b-a12b:free"),
        ("gemini", "gemini-2.5-flash"),
        ("groq", "openai/gpt-oss-120b"),
    ],
)
async def test_other_providers_omit_reasoning_effort(
    anyio_backend, route, provider, model_name, monkeypatch
):
    assert anyio_backend == "asyncio"
    captured: list[dict[str, Any]] = []
    chat_model = _mock_model(
        captured=captured,
        model_name=model_name,
        endpoint="https://integrate.api.nvidia.com/v1",
    )

    sm = ProviderStructuredModel(provider, model_name)
    monkeypatch.setattr(sm, "_models", lambda: [(provider, chat_model)])

    result = await sm.generate(
        schema=_Ping,
        prompt="test prompt",
        payload={"query": "celtics"},
        envelope=_envelope(provider=provider, model=model_name, route=route),
    )
    assert isinstance(result, _Ping)
    assert len(captured) == 1
    assert "reasoning_effort" not in captured[0]
    assert captured[0].get("max_tokens") is None
    assert captured[0].get("max_completion_tokens") is None
