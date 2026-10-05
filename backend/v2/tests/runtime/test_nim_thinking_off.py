from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from openai.types.chat import ChatCompletion
from pydantic import BaseModel
from v2.adapters.models import DimeOpenAIChatModel
from v2.adapters.structured import EndpointCapabilities
from pydantic_ai.providers.openai import OpenAIProvider

from shared.config import settings
from shared.providers import NVIDIA_NIM_MODELS

from v2.adapters.models import (
    ProviderStructuredModel,
    ReasoningContentFallbackClient,
    RecordedStructuredModel,
)
from v2.runtime import RequestEnvelope
from v2.runtime.ledger import LedgerKind, RunLedger


class _Ping(BaseModel):
    answer: str


def _completion_body(
    *,
    content: Any,
    reasoning_content: Any,
    finish_reason: Any = "stop",
    model: str,
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
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }
    ).model_dump(mode="json")


def _capturing_client(
    *,
    thinking_off: bool,
    content: Any = '{"answer":"hi"}',
    reasoning_content: Any = None,
    finish_reason: Any = "stop",
    model: str = "test-model/nim-flash",
    captured: list[dict[str, Any]],
) -> ReasoningContentFallbackClient:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content.decode()))
        return httpx.Response(
            200,
            json=_completion_body(
                content=content,
                reasoning_content=reasoning_content,
                finish_reason=finish_reason,
                model=model,
            ),
        )

    transport = httpx.MockTransport(handler)
    return ReasoningContentFallbackClient(
        api_key="placeholder",
        http_client=httpx.AsyncClient(transport=transport),
        thinking_off=thinking_off,
    )


def _intake_envelope(*, model: str = "test-model/nim-flash") -> RequestEnvelope:
    return RequestEnvelope.freeze(
        provider="nvidia",
        model=model,
        route="intake",
        prompt="p",
        context={},
        tool_schemas={},
        planner_version="v2",
    )


def _clear_provider_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for attr in (
        "nvidia_nim_api_key",
        "mistral_api_key",
        "openrouter_api_key",
        "inception_api_key",
        "groq_api_key",
    ):
        monkeypatch.setattr(settings, attr, "")


@pytest.mark.anyio
@pytest.mark.parametrize("thinking_off,extra_body,expected_kwargs", [
    (True, None, {"enable_thinking": False}),
    (False, None, None),
    (True, {"some_flag": True,
            "chat_template_kwargs": {"enable_thinking": True, "other": 1}},
     {"enable_thinking": False, "other": 1}),
])
async def test_thinking_off_wire_body(thinking_off, extra_body,
                                      expected_kwargs):
    captured: list[dict[str, Any]] = []
    client = _capturing_client(thinking_off=thinking_off, captured=captured)
    kwargs: dict[str, Any] = {
        "model": "test-model/nim-flash",
        "messages": [{"role": "user", "content": "hi"}],
        "response_format": {"type": "json_object"},
    }
    if extra_body is not None:
        kwargs["extra_body"] = extra_body
    resp = await client.chat.completions.create(**kwargs)
    assert resp.choices[0].message.content == '{"answer":"hi"}'
    assert len(captured) == 1
    if expected_kwargs is None:
        assert "chat_template_kwargs" not in captured[0]
    else:
        assert captured[0]["chat_template_kwargs"] == expected_kwargs
        if extra_body is not None:
            assert captured[0]["some_flag"] is True


@pytest.mark.parametrize("model", [*list(NVIDIA_NIM_MODELS),
                                   "not-on/the-allowlist"])
def test_nim_wiring_enables_thinking_off(
    monkeypatch: pytest.MonkeyPatch, model: str
):
    _clear_provider_keys(monkeypatch)
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "placeholder")
    structured = ProviderStructuredModel("nvidia", model)
    models = structured._models()
    nvidia_models = [(p, m) for p, m in models if p == "nvidia"]
    assert len(nvidia_models) == 1
    client = nvidia_models[0][1].client
    assert isinstance(client, ReasoningContentFallbackClient)
    assert client.thinking_off is True


@pytest.mark.parametrize(
    "provider,key_attr",
    [("mistral", "mistral_api_key"), ("groq", "groq_api_key")],
)
def test_non_nim_providers_keep_thinking_off_disabled(
    monkeypatch: pytest.MonkeyPatch, provider: str, key_attr: str
):
    _clear_provider_keys(monkeypatch)
    monkeypatch.setattr(settings, key_attr, "placeholder")
    if provider == "groq":
        monkeypatch.setattr(settings, "dime_enable_groq", True)
    structured = ProviderStructuredModel(provider, "whatever")
    models = structured._models()
    assert len(models) == 1
    named_provider, model = models[0]
    assert named_provider == provider
    client = model.client
    assert isinstance(client, ReasoningContentFallbackClient)
    assert client.thinking_off is False


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_generate_sends_thinking_off_wire_body(
    anyio_backend,
    monkeypatch: pytest.MonkeyPatch,
):
    assert anyio_backend == "asyncio"
    captured: list[dict[str, Any]] = []
    mock_client = _capturing_client(thinking_off=True, captured=captured)
    openai_model = DimeOpenAIChatModel(
        "test-model/nim-flash",
        provider=OpenAIProvider(openai_client=mock_client),
        capabilities=EndpointCapabilities(
            endpoint="https://integrate.api.nvidia.com/v1",
            strict_json_schema=True, tool_calling=True,
            strict_tool_definitions=True),
    )
    monkeypatch.setattr(
        ProviderStructuredModel, "_models", lambda self: [("nvidia", openai_model)]
    )
    structured = ProviderStructuredModel("nvidia", "test-model/nim-flash")
    result = await structured.generate(
        schema=_Ping, prompt="p", payload={}, envelope=_intake_envelope()
    )
    assert result.answer == "hi"
    assert len(captured) == 1
    assert captured[0]["chat_template_kwargs"] == {"enable_thinking": False}


def test_no_model_name_branching_in_thinking_off_wiring():
    source = (
        Path(__file__).resolve().parents[2] / "adapters" / "models.py"
    ).read_text()
    thinking_off_lines = [
        line for line in source.splitlines() if "thinking_off" in line
    ]
    assert thinking_off_lines, "thinking_off wiring must exist in models.py"
    banned = ("deepseek", "glm", "z-ai", "v4.1", "v4-1")
    for line in thinking_off_lines:
        lowered = line.lower()
        for token in banned:
            assert token not in lowered, (
                f"model-name branching in thinking-off wiring: {line.strip()}"
            )
    assert 'thinking_off=(provider == "nvidia")' in source


@pytest.mark.anyio
async def test_promotion_still_applies_with_thinking_off():
    captured: list[dict[str, Any]] = []
    client = _capturing_client(
        thinking_off=True,
        content="",
        reasoning_content='{"answer":"hi"}',
        finish_reason="stop",
        captured=captured,
    )
    resp = await client.chat.completions.create(
        model="test-model/nim-flash",
        messages=[{"role": "user", "content": "hi"}],
        response_format={"type": "json_object"},
    )
    assert resp.choices[0].message.content == '{"answer":"hi"}'
    assert captured[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert client.reasoning_content_promotions == [
        {
            "choice_index": 0,
            "finish_reason": "stop",
            "reasoning_content_chars": len('{"answer":"hi"}'),
        }
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("finish_reason", ["length", "content_filter"])
async def test_no_promotion_unless_stop_with_thinking_off(finish_reason: str):
    captured: list[dict[str, Any]] = []
    client = _capturing_client(
        thinking_off=True,
        content="",
        reasoning_content='{"answer":"hi"}',
        finish_reason=finish_reason,
        captured=captured,
    )
    resp = await client.chat.completions.create(
        model="test-model/nim-flash",
        messages=[{"role": "user", "content": "hi"}],
        response_format={"type": "json_object"},
    )
    assert resp.choices[0].message.content == ""
    assert client.reasoning_content_promotions == []


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_promotion_recorded_on_attempt_ledger(
    anyio_backend,
    monkeypatch: pytest.MonkeyPatch,
):
    assert anyio_backend == "asyncio"
    captured: list[dict[str, Any]] = []
    mock_client = _capturing_client(
        thinking_off=True,
        content="",
        reasoning_content='{"answer":"hi"}',
        finish_reason="stop",
        captured=captured,
    )
    openai_model = DimeOpenAIChatModel(
        "test-model/nim-flash",
        provider=OpenAIProvider(openai_client=mock_client),
        capabilities=EndpointCapabilities(
            endpoint="https://integrate.api.nvidia.com/v1",
            strict_json_schema=True, tool_calling=True,
            strict_tool_definitions=True),
    )
    monkeypatch.setattr(
        ProviderStructuredModel, "_models", lambda self: [("nvidia", openai_model)]
    )
    structured = ProviderStructuredModel("nvidia", "test-model/nim-flash")
    ledger = RunLedger(run_id="run-1")
    recorded = RecordedStructuredModel(structured, ledger, turn_id="t1")
    result = await recorded.generate(
        schema=_Ping, prompt="p", payload={}, envelope=_intake_envelope()
    )
    assert result.answer == "hi"
    attempts = [
        entry
        for entry in ledger.entries
        if entry.kind == LedgerKind.ASSISTANT_ATTEMPT
    ]
    assert len(attempts) == 1
    data = attempts[0].data
    assert data["status"] == "accepted"
    assert data["used_fallback"] is False
    assert data["reasoning_content_promotions"] == [
        {
            "provider": "nvidia",
            "choice_index": 0,
            "finish_reason": "stop",
            "reasoning_content_chars": len('{"answer":"hi"}'),
        }
    ]
    assert structured.last_promotions == data["reasoning_content_promotions"]
