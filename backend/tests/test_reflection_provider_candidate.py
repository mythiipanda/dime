from __future__ import annotations

import inspect
import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel
from shared import providers
from shared.config import settings
from v2.adapters.models import ProviderStructuredModel
from v2.adapters.structured import OutputStrategy, Support, capabilities_for
from v2.runtime import RequestEnvelope

class Ping(BaseModel):
    answer: str

def _completion(content: str) -> dict[str, Any]:
    return {
        "id": "completion-reflect", "created": 1,
        "model": "Beam-1.0-501B-A23B", "object": "chat.completion",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": content}}],
    }

class Wire:
    def __init__(self, bodies: list[dict[str, Any]]) -> None:
        self._bodies = list(bodies)
        self.requests: list[httpx.Request] = []
        self.sent: list[dict[str, Any]] = []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            self.sent.append(json.loads(request.content))
            index = min(len(self.sent) - 1, len(self._bodies) - 1)
            return httpx.Response(200, json=self._bodies[index])
        return httpx.MockTransport(handler)

@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"

@pytest.fixture
def reflection_enabled(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(settings, "reflection_api_key", "reflection-key")
    monkeypatch.setattr(settings, "dime_enable_reflection", True)
    monkeypatch.setattr(settings, "reflection_model", "")
    return settings

def test_the_route_resolves_the_pinned_model_and_its_alias(reflection_enabled: Any) -> None:
    assert providers.resolve_model_id("reflection:beam-1") == (
        "reflection", "Beam-1.0-501B-A23B")
    assert providers.resolve_model_id(
        "reflection:Beam-1.0-501B-A23B") == (
            "reflection", "Beam-1.0-501B-A23B")

def test_the_route_is_a_verified_https_endpoint() -> None:
    assert providers.REFLECTION_BASE_URL == "https://api.reflection.ai/openai/v1"

def test_an_unapproved_reflection_model_fails_closed(reflection_enabled: Any) -> None:
    for slug in ("beam-2", "", "Beam-1.0-501B-A23B ", "gpt-4o"):
        with pytest.raises(providers.ProviderPolicyError,
                           match="unapproved Reflection model"):
            providers.resolve_model_id("reflection:" + slug)

def test_the_route_needs_both_the_key_and_the_explicit_enable(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "reflection_api_key", "")
    monkeypatch.setattr(settings, "dime_enable_reflection", True)
    with pytest.raises(providers.ProviderPolicyError, match="not activated"):
        providers.resolve_model_id("reflection:beam-1")
    monkeypatch.setattr(settings, "reflection_api_key", "reflection-key")
    monkeypatch.setattr(settings, "dime_enable_reflection", False)
    with pytest.raises(providers.ProviderPolicyError, match="not activated"):
        providers.resolve_model_id("reflection:beam-1")

def test_reflection_never_enters_the_automatic_fallback_chain(
        reflection_enabled: Any) -> None:
    assert "reflection" not in providers.active_provider_order()
    for primary in ("gemini", "openrouter", "inception", "reflection"):
        assert "reflection" not in providers.fallback_order(primary)


def test_the_catalog_registers_the_route_when_enabled_and_keyed(
        reflection_enabled: Any) -> None:
    catalog = providers.models_catalog()
    assert catalog["available"]["reflection"] is True
    option = next(
        item for item in catalog["models"]
        if item["engine"] == "reflection")
    assert option["id"] == "reflection:Beam-1.0-501B-A23B"
    assert option["available"] is True


def test_the_catalog_omits_the_route_when_not_enabled_or_keyed(
        reflection_enabled: Any) -> None:
    settings.dime_enable_reflection = False
    catalog = providers.models_catalog()
    assert "reflection" not in catalog["available"]
    assert not [item for item in catalog["models"]
                if item["engine"] == "reflection"]
    settings.dime_enable_reflection = True
    settings.reflection_api_key = ""
    catalog = providers.models_catalog()
    assert "reflection" not in catalog["available"]
    assert not [item for item in catalog["models"]
                if item["engine"] == "reflection"]


@pytest.mark.anyio
async def test_reflection_http_failures_stay_transparent(
        monkeypatch: pytest.MonkeyPatch,
        reflection_enabled: Any) -> None:
    for status in (401, 429, 500):
        def failed(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status, json={"error": "route failure"})
        transport = httpx.MockTransport(failed)
        client = httpx.AsyncClient(transport=transport)
        model = ProviderStructuredModel(
            "reflection", "Beam-1.0-501B-A23B", http_client=client)
        envelope = RequestEnvelope.freeze(
            provider="reflection", model="Beam-1.0-501B-A23B",
            route="intake", prompt="stage instructions", context={},
            tool_schemas={}, planner_version="v2")
        with pytest.raises(RuntimeError):
            await model.generate(
                schema=Ping, prompt="stage instructions", payload={},
                envelope=envelope)
        assert model.last_failures
        assert model.last_failures[0]["provider"] == "reflection"


@pytest.mark.anyio
async def test_reflection_malformed_payload_stays_transparent(
        reflection_enabled: Any) -> None:
    wire = Wire([{
        "id": "completion-reflect", "created": 1,
        "model": "Beam-1.0-501B-A23B", "object": "chat.completion",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant",
                                 "content": "not json"}}]}])
    client = httpx.AsyncClient(transport=wire.transport())
    model = ProviderStructuredModel(
        "reflection", "Beam-1.0-501B-A23B", http_client=client)
    envelope = RequestEnvelope.freeze(
        provider="reflection", model="Beam-1.0-501B-A23B",
        route="intake", prompt="stage instructions", context={},
        tool_schemas={}, planner_version="v2")
    with pytest.raises(RuntimeError):
        await model.generate(
            schema=Ping, prompt="stage instructions", payload={},
            envelope=envelope)
    assert model.last_failures

def test_reflection_is_priced_as_an_allowlisted_free_beta(
        reflection_enabled: Any) -> None:
    assert providers.is_free_model(
        "reflection", providers.REFLECTION_DEFAULT) is True
    assert providers.is_free_model("reflection", "gpt-4o") is False

def test_the_selected_route_reaches_the_adapter_from_settings(
        reflection_enabled: Any) -> None:
    provider, model_name = providers.resolve_model_id("reflection:beam-1")
    wire = Wire([_completion('{"answer": "a"}')])
    client = httpx.AsyncClient(transport=wire.transport())
    models = ProviderStructuredModel(
        provider, model_name, http_client=client)._models()
    assert [name for name, _ in models] == ["reflection"]
    assert models[0][1].model_name == "Beam-1.0-501B-A23B"

def test_the_adapter_wires_the_settings_key_model_and_endpoint(
        reflection_enabled: Any) -> None:
    wire = Wire([_completion('{"answer": "a"}')])
    client = httpx.AsyncClient(transport=wire.transport())
    models = ProviderStructuredModel(
        "reflection", "Beam-1.0-501B-A23B", http_client=client)._models()
    assert len(models) == 1
    provider, chat = models[0]
    assert provider == "reflection"
    assert chat.model_name == "Beam-1.0-501B-A23B"
    assert str(chat.client.base_url).rstrip("/") == providers.REFLECTION_BASE_URL
    assert chat.client.api_key == "reflection-key"

def test_the_adapter_fails_closed_when_the_route_is_not_enabled(
        monkeypatch: pytest.MonkeyPatch) -> None:
    wire = Wire([_completion('{"answer": "a"}')])
    client = httpx.AsyncClient(transport=wire.transport())
    monkeypatch.setattr(settings, "reflection_api_key", "retained-key")
    monkeypatch.setattr(settings, "dime_enable_reflection", False)
    assert ProviderStructuredModel(
        "reflection", "Beam-1.0-501B-A23B", http_client=client)._models() == []
    monkeypatch.setattr(settings, "dime_enable_reflection", True)
    monkeypatch.setattr(settings, "reflection_api_key", "")
    assert ProviderStructuredModel(
        "reflection", "Beam-1.0-501B-A23B", http_client=client)._models() == []

def test_the_unmeasured_reflection_endpoint_starts_on_the_prompt_floor() -> None:
    capabilities = capabilities_for(providers.REFLECTION_BASE_URL)
    assert capabilities.measurement is None
    assert capabilities.strict_json_schema is Support.UNMEASURED
    assert capabilities.tool_calling is Support.UNMEASURED
    assert capabilities.strict_tool_definitions is Support.UNMEASURED

def test_the_reflection_route_does_not_disable_tls_verification() -> None:
    import v2.adapters.models as adapter
    for module in (providers, adapter, settings.__class__):
        source = inspect.getsource(module).casefold()
        for forbidden in ("verify=false", "cert_none",
                          "_create_unverified", "insecure_tls"):
            assert forbidden not in source

@pytest.mark.anyio
async def test_a_stage_request_hits_the_reflection_route_with_the_pinned_model(
        reflection_enabled: Any) -> None:
    wire = Wire([_completion('{"answer": "a"}')])
    client = httpx.AsyncClient(transport=wire.transport())
    model = ProviderStructuredModel(
        "reflection", "Beam-1.0-501B-A23B", http_client=client)
    envelope = RequestEnvelope.freeze(
        provider="reflection", model="Beam-1.0-501B-A23B", route="intake",
        prompt="stage instructions", context={}, tool_schemas={},
        planner_version="v2")
    payload = {"season": "2025-26"}
    result = await model.generate(
        schema=Ping, prompt="stage instructions", payload=payload,
        envelope=envelope)
    assert result == Ping(answer="a")
    assert model.last_provider == "reflection"
    assert model.last_model == "Beam-1.0-501B-A23B"
    assert model.last_output_strategy is OutputStrategy.PROMPTED_JSON
    request = wire.requests[0]
    assert request.method == "POST"
    assert request.url.host == "api.reflection.ai"
    assert request.url.path == "/openai/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer reflection-key"
    body = wire.sent[0]
    assert body["model"] == "Beam-1.0-501B-A23B"
    assert body["response_format"] == {"type": "json_object"}
    assert "tools" not in body
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][0]["content"] == "stage instructions"
    transcript = "\n".join(
        str(message["content"]) for message in body["messages"])
    assert '"answer"' in transcript
    assert json.dumps(payload, sort_keys=True) in transcript
    assert body["messages"][-1]["role"] == "user"
