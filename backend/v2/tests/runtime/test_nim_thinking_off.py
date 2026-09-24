from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from openai.types.chat import ChatCompletion
from pydantic import BaseModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import settings
from app.providers import NVIDIA_NIM_MODELS

from v2.adapters.models import (
    NIM_THINKING_OFF_EXTRA_BODY,
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


# (a) the thinking-off setting is on every NIM structured request -----------
@pytest.mark.anyio
async def test_thinking_off_body_sent_on_nim_request():
    captured: list[dict[str, Any]] = []
    client = _capturing_client(thinking_off=True, captured=captured)
    resp = await client.chat.completions.create(
        model="test-model/nim-flash",
        messages=[{"role": "user", "content": "hi"}],
        response_format={"type": "json_object"},
    )
    assert resp.choices[0].message.content == '{"answer":"hi"}'
    assert len(captured) == 1
    assert captured[0]["chat_template_kwargs"] == {"enable_thinking": False}


@pytest.mark.anyio
async def test_thinking_off_not_sent_by_default():
    captured: list[dict[str, Any]] = []
    client = _capturing_client(thinking_off=False, captured=captured)
    await client.chat.completions.create(
        model="test-model/nim-flash",
        messages=[{"role": "user", "content": "hi"}],
        response_format={"type": "json_object"},
    )
    assert "chat_template_kwargs" not in captured[0]


@pytest.mark.anyio
async def test_thinking_off_preserves_caller_extra_body():
    captured: list[dict[str, Any]] = []
    client = _capturing_client(thinking_off=True, captured=captured)
    await client.chat.completions.create(
        model="test-model/nim-flash",
        messages=[{"role": "user", "content": "hi"}],
        extra_body={
            "some_flag": True,
            "chat_template_kwargs": {"enable_thinking": True, "other": 1},
        },
    )
    body = captured[0]
    assert body["some_flag"] is True
    assert body["chat_template_kwargs"] == {
        "enable_thinking": False,
        "other": 1,
    }


def test_wire_shape_constant_is_exact():
    assert NIM_THINKING_OFF_EXTRA_BODY == {
        "chat_template_kwargs": {"enable_thinking": False}
    }


@pytest.mark.parametrize("model", list(NVIDIA_NIM_MODELS))
def test_nim_wiring_enables_thinking_off_for_every_nim_model(
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


def test_nim_wiring_enables_thinking_off_for_unapproved_slug(
    monkeypatch: pytest.MonkeyPatch,
):
    _clear_provider_keys(monkeypatch)
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "placeholder")
    structured = ProviderStructuredModel("nvidia", "not-on/the-allowlist")
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
async def test_generate_sends_thinking_off_wire_body(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: list[dict[str, Any]] = []
    mock_client = _capturing_client(thinking_off=True, captured=captured)
    openai_model = OpenAIChatModel(
        "test-model/nim-flash",
        provider=OpenAIProvider(openai_client=mock_client),
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


# (b) no model-name branching (static check) ---------------------------------
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


# (c) promotion fallback still intact -----------------------------------------
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
async def test_promotion_recorded_on_attempt_ledger(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: list[dict[str, Any]] = []
    mock_client = _capturing_client(
        thinking_off=True,
        content="",
        reasoning_content='{"answer":"hi"}',
        finish_reason="stop",
        captured=captured,
    )
    openai_model = OpenAIChatModel(
        "test-model/nim-flash",
        provider=OpenAIProvider(openai_client=mock_client),
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
