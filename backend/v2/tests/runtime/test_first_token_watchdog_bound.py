from __future__ import annotations

import time

import anyio
import pytest

from v2.adapters.models import (
    DimeOpenAIChatModel,
    ModelBudgets,
    ProviderStructuredModel,
    ReasoningContentFallbackClient,
    RoutePolicy,
    load_model_budgets,
    route_budgets,
)
from v2.adapters.structured import EndpointCapabilities, Support
from v2.contracts import TaskSpec
from v2.runtime import RequestEnvelope

WATCHDOG_S = 1.0
ROUTE_WATCHDOG_S = 2.0
REAL_SLEEP = anyio.sleep

def _planner_envelope():
    return RequestEnvelope.freeze(
        provider="inception", model="primary", route="planner",
        prompt="p", context={}, tool_schemas={}, planner_version="v2")

def _stage_model(budgets: ModelBudgets) -> ProviderStructuredModel:
    import httpx
    from pydantic_ai.providers.openai import OpenAIProvider
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(500, json={"error": {"message": "x"}})))
    chat_model = DimeOpenAIChatModel(
        "primary",
        provider=OpenAIProvider(openai_client=ReasoningContentFallbackClient(
            api_key="stub", max_retries=0, http_client=client)),
        capabilities=EndpointCapabilities(
            endpoint="https://stub.invalid/v1",
            strict_json_schema=Support.MEASURED, tool_calling=Support.MEASURED,
            strict_tool_definitions=Support.MEASURED))
    model = ProviderStructuredModel("inception", "primary", model_budgets=budgets)
    model._models = lambda: [("inception", chat_model)]
    return model

def _watchdog() -> ModelBudgets:
    return ModelBudgets(
        transport_timeout_s=600.0,
        defaults=RoutePolicy(attempt_timeout_s=WATCHDOG_S,
                             total_budget_s=ROUTE_WATCHDOG_S),
        routes={})

def test_the_shipped_watchdog_is_off_and_the_knob_exists():
    assert route_budgets(None, "planner") == RoutePolicy()
    assert load_model_budgets().routes == {}

@pytest.mark.anyio
async def test_never_tokens_hang_is_bounded_when_a_watchdog_is_configured(
        monkeypatch):
    monkeypatch.setattr("v2.adapters.models.anyio.sleep", _no_sleep)

    class HangingAgent:
        def __init__(self, *a, **k):
            pass

        async def run(self, prompt):
            await anyio.sleep_forever()

    monkeypatch.setattr("v2.adapters.models.Agent", HangingAgent)
    model = _stage_model(_watchdog())
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="all structured-output providers failed"):
        await model.generate(schema=TaskSpec, prompt="p",
                             payload={"q": "x"}, envelope=_planner_envelope())
    elapsed = time.monotonic() - started
    assert ROUTE_WATCHDOG_S - 0.5 <= elapsed <= ROUTE_WATCHDOG_S + 5.0
    assert [failure["message_class"] for failure in model.last_failures] == [
        "timeout", "timeout", "planner_deadline"]
    print(f"\nnever-tokens planner hang resolved in {elapsed:.2f}s "
          f"(watchdog {ROUTE_WATCHDOG_S}s)")

@pytest.mark.anyio
async def test_slow_dribble_hang_is_bounded_when_a_watchdog_is_configured(
        monkeypatch):
    monkeypatch.setattr("v2.adapters.models.anyio.sleep", _no_sleep)

    class DribblingAgent:
        def __init__(self, *a, **k):
            pass

        async def run(self, prompt):
            for _ in range(1000):
                await REAL_SLEEP(0.2)

    monkeypatch.setattr("v2.adapters.models.Agent", DribblingAgent)
    model = _stage_model(_watchdog())
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="all structured-output providers failed"):
        await model.generate(schema=TaskSpec, prompt="p",
                             payload={"q": "x"}, envelope=_planner_envelope())
    elapsed = time.monotonic() - started
    assert ROUTE_WATCHDOG_S - 0.5 <= elapsed <= ROUTE_WATCHDOG_S + 5.0
    assert len(model.last_failures) == 3
    print(f"\nslow-dribble planner hang resolved in {elapsed:.2f}s "
          f"(watchdog {ROUTE_WATCHDOG_S}s)")

@pytest.mark.anyio
async def test_healthy_provider_unaffected(monkeypatch):
    class HealthyAgent:
        def __init__(self, *a, **k):
            pass

        async def run(self, prompt):
            return type("R", (), {
                "output": TaskSpec(goal="ok", mode="quick",
                                   deliverable="x")})()

    monkeypatch.setattr("v2.adapters.models.Agent", HealthyAgent)
    model = _stage_model(_watchdog())
    started = time.monotonic()
    out = await model.generate(schema=TaskSpec, prompt="p",
                               payload={"q": "x"}, envelope=_planner_envelope())
    elapsed = time.monotonic() - started
    assert out.goal == "ok"
    assert elapsed < 2.0
    assert model.last_failures == []
    print(f"\nhealthy planner call resolved in {elapsed:.3f}s")

async def _no_sleep(value: float) -> None:
    return None
