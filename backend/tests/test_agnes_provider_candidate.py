from __future__ import annotations

import json

import httpx
import pytest

from shared import providers
from shared.config import settings
from v2.adapters.models import ProviderStructuredModel


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_agnes_is_opt_in_and_ordered_after_groq_before_gemini(monkeypatch):
    for name in (
        "cerebras_api_key", "nvidia_nim_api_key", "openrouter_api_key",
        "mistral_api_key",
    ):
        monkeypatch.setattr(settings, name, "")
    monkeypatch.setattr(settings, "dime_enable_inception", False)
    monkeypatch.setattr(settings, "dime_enable_groq", True)
    monkeypatch.setattr(settings, "groq_api_key", "fake-groq")
    monkeypatch.setattr(settings, "dime_enable_agnes", True)
    monkeypatch.setattr(settings, "agnes_api_key", "fake-agnes")
    monkeypatch.setattr(settings, "gemini_api_key", "fake-gemini")
    order = providers.active_provider_order()
    assert order[:3] == ("groq", "agnes", "gemini")
    assert providers._default_provider() == ("groq", providers.GROQ_DEFAULT)


def test_agnes_missing_key_or_enable_flag_is_inactive(monkeypatch):
    monkeypatch.setattr(settings, "dime_enable_agnes", True)
    monkeypatch.setattr(settings, "agnes_api_key", "")
    assert "agnes" not in providers.active_provider_order()
    assert providers.get_llm("agnes") is None
    with pytest.raises(providers.ProviderPolicyError, match="not activated"):
        providers.resolve_model_id("agnes:agnes-3.0-flash")

    monkeypatch.setattr(settings, "agnes_api_key", "fake-agnes")
    monkeypatch.setattr(settings, "dime_enable_agnes", False)
    assert "agnes" not in providers.active_provider_order()
    assert providers.get_llm("agnes") is None


@pytest.mark.parametrize("model", ["agnes-3.0-pro", "agnes-2.5-pro", "gpt-4o", ""])
def test_agnes_paid_or_unlisted_models_fail_closed(monkeypatch, model):
    monkeypatch.setattr(settings, "dime_enable_agnes", True)
    monkeypatch.setattr(settings, "agnes_api_key", "fake-agnes")
    with pytest.raises(providers.ProviderPolicyError, match="unapproved Agnes model"):
        providers.resolve_model_id("agnes:" + model)
    with pytest.raises(providers.ProviderPolicyError, match="unapproved Agnes model"):
        providers.get_llm("agnes", model)


def test_agnes_client_uses_allowlisted_https_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "dime_enable_agnes", True)
    monkeypatch.setattr(settings, "agnes_api_key", "fake-agnes")
    client = providers.get_llm("agnes")
    assert client is not None
    assert client.model_name == "agnes-3.0-flash"
    assert str(client.openai_api_base).rstrip("/") == providers.AGNES_BASE_URL
    assert client.openai_api_key.get_secret_value() == "fake-agnes"
    assert client.max_retries == 0


@pytest.mark.anyio
async def test_agnes_structured_adapter_fake_transport(monkeypatch):
    monkeypatch.setattr(settings, "dime_enable_agnes", True)
    monkeypatch.setattr(settings, "agnes_api_key", "fake-agnes")
    sent: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={
            "id": "fake-completion", "created": 1,
            "model": "agnes-3.0-flash", "object": "chat.completion",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": '{"value":"ok"}'}}],
        })

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    adapter = ProviderStructuredModel("agnes", "agnes-3.0-flash", http_client=client)
    assert [provider for provider, _ in adapter._models()] == ["agnes"]
    from pydantic import BaseModel
    from v2.runtime import RequestEnvelope

    class Result(BaseModel):
        value: str

    envelope = RequestEnvelope.freeze(
        provider="agnes", model="agnes-3.0-flash", route="intake",
        prompt="fixture only", context={}, tool_schemas={}, planner_version="v2")
    try:
        result = await adapter.generate(
            schema=Result, prompt="fixture only", payload={}, envelope=envelope)
    finally:
        await client.aclose()
    assert result.value == "ok"
    assert adapter.last_provider == "agnes"
    assert adapter.last_model == "agnes-3.0-flash"
    assert len(sent) == 1
    assert sent[0].url.scheme == "https"
    assert sent[0].url.host == "apihub.agnes-ai.com"
    assert json.loads(sent[0].content)["model"] == "agnes-3.0-flash"
    assert sent[0].headers["authorization"] == "Bearer fake-agnes"


def test_catalog_registers_only_enabled_agnes_models(monkeypatch):
    monkeypatch.setattr(settings, "dime_enable_agnes", True)
    monkeypatch.setattr(settings, "agnes_api_key", "fake-agnes")
    catalog = providers.models_catalog()
    choices = [item for item in catalog["models"] if item["engine"] == "agnes"]
    assert {item["id"] for item in choices} == {
        "agnes:agnes-3.0-flash", "agnes:agnes-2.5-flash"}
    assert all(item["available"] for item in choices)
