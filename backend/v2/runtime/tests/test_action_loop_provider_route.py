from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from openai.types.chat import ChatCompletion
from pydantic_ai.providers.openai import OpenAIProvider

from v2.adapters.models import (
    DimeOpenAIChatModel, ProviderStructuredModel, ReasoningContentFallbackClient,
    RecordedStructuredModel, provider_route_prompt,
)
from v2.adapters.structured import EndpointCapabilities, Support
from v2.runtime.action_loop import LoopAction
from v2.runtime.ledger import LedgerKind, RequestEnvelope, RunLedger


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _completion(content: str) -> dict[str, Any]:
    return ChatCompletion.model_validate({
        "id": "chatcmpl-test",
        "created": 1700000000,
        "model": "Beam-1.0-501B-A23B",
        "object": "chat.completion",
        "choices": [{
            "finish_reason": "stop",
            "index": 0,
            "message": {"role": "assistant", "content": content},
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                  "total_tokens": 15},
    }).model_dump(mode="json")


def _model(captured: list[dict[str, Any]], content: str) -> DimeOpenAIChatModel:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content.decode()))
        return httpx.Response(200, json=_completion(content))

    client = ReasoningContentFallbackClient(
        api_key="placeholder",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return DimeOpenAIChatModel(
        "Beam-1.0-501B-A23B",
        provider=OpenAIProvider(openai_client=client),
        capabilities=EndpointCapabilities(
            endpoint="https://api.reflection.ai/openai/v1",
            strict_json_schema=Support.MEASURED,
            tool_calling=Support.MEASURED,
            strict_tool_definitions=Support.MEASURED))


def _envelope(route: str) -> RequestEnvelope:
    prompt = provider_route_prompt("action_loop", "action_loop")
    return RequestEnvelope.freeze(
        provider="reflection", model="Beam-1.0-501B-A23B",
        route=route, prompt=prompt, context={"task": "wins"},
        tool_schemas=LoopAction.model_json_schema(), planner_version="v2",
        output_strategy="prompted_json")


@pytest.mark.anyio
async def test_action_loop_provider_route_reaches_ledger(monkeypatch):
    captured: list[dict[str, Any]] = []
    content = json.dumps({
        "step": {"action": "tool", "capability": "standings",
                 "node_id": "facts", "arguments": {"season": "2024-25"}}
    })
    provider = ProviderStructuredModel("reflection", "Beam-1.0-501B-A23B")
    monkeypatch.setattr(
        provider, "_models", lambda: [("reflection", _model(captured, content))])
    ledger = RunLedger("route-test")
    recorded = RecordedStructuredModel(provider, ledger, turn_id="route-test")

    result = await recorded.generate(
        schema=LoopAction,
        prompt=provider_route_prompt("action_loop", "action_loop"),
        payload={"task": "wins"}, envelope=_envelope("action_loop"))

    assert result.step.action == "tool"
    assert result.step.capability == "standings"
    assert len(captured) == 1
    kinds = [item.kind for item in ledger.entries]
    assert LedgerKind.MODEL_REQUEST in kinds
    assert LedgerKind.ASSISTANT_ATTEMPT in kinds
    attempt = next(item for item in ledger.entries
                   if item.kind == LedgerKind.ASSISTANT_ATTEMPT)
    assert attempt.data["status"] == "accepted"
    request = next(item for item in ledger.entries
                   if item.kind == LedgerKind.MODEL_REQUEST)
    assert request.data["route"] == "action_loop"


def test_unknown_provider_route_still_rejected():
    with pytest.raises(ValueError, match="provider route"):
        provider_route_prompt("unknown_route", "unknown_route")
