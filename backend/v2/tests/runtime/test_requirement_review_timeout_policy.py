from __future__ import annotations

from contextlib import contextmanager

import httpx
import pytest
from pydantic_ai.providers.openai import OpenAIProvider

from v2.adapters.models import (
    DimeOpenAIChatModel,
    ModelBudgets,
    ProviderStructuredModel,
    ReasoningContentFallbackClient,
    RoutePolicy,
)
from v2.adapters.structured import EndpointCapabilities, Support
from v2.contracts import RequirementReview
from v2.runtime import RequestEnvelope

ATTEMPT_BUDGET_S = 30.0
ROUTE_BUDGET_S = 60.0

def _envelope() -> RequestEnvelope:
    return RequestEnvelope.freeze(
        provider="inception", model="primary", route="requirement_review",
        prompt="p", context={}, tool_schemas={}, planner_version="v2")

def _stage_model(budgets: ModelBudgets | None = None) -> ProviderStructuredModel:
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

def _configured_budgets() -> ModelBudgets:
    return ModelBudgets(
        transport_timeout_s=600.0,
        defaults=RoutePolicy(attempt_timeout_s=ATTEMPT_BUDGET_S),
        routes={"requirement_review": RoutePolicy(
            attempt_timeout_s=ATTEMPT_BUDGET_S, total_budget_s=ROUTE_BUDGET_S)})

def _budgeted_clock(monkeypatch, seconds: float) -> dict:
    clock = {"value": 0.0}
    calls: list[str] = []
    budgets_seen: list[float] = []

    class Agent:
        def __init__(self, model, *args, **kwargs):
            calls.append(model.model_name)
            budgets_seen.append(seconds)

        async def run(self, prompt):
            clock["value"] += seconds
            raise TimeoutError("bounded")

    @contextmanager
    def fail_after(timeout):
        started = clock["value"]
        yield
        if clock["value"] - started > timeout:
            raise TimeoutError("attempt timed out")

    async def no_sleep(value):
        return None

    monkeypatch.setattr("v2.adapters.models.Agent", Agent)
    monkeypatch.setattr("v2.adapters.models.anyio.fail_after", fail_after)
    monkeypatch.setattr("v2.adapters.models.anyio.sleep", no_sleep)
    monkeypatch.setattr("v2.adapters.models.random.uniform", lambda a, b: 0)
    monkeypatch.setattr("v2.adapters.models.time.monotonic", lambda: clock["value"])
    monkeypatch.setattr(
        "v2.adapters.models.time.perf_counter", lambda: clock["value"])
    return {"clock": clock, "calls": calls, "budgets": budgets_seen}

@pytest.mark.anyio
async def test_a_configured_requirement_review_budget_bounds_the_attempt(
        monkeypatch):
    state = _budgeted_clock(monkeypatch, 5.25)

    class QuickAgent:
        def __init__(self, *args, **kwargs): pass
        async def run(self, prompt):
            state["clock"]["value"] += 5.25
            return type("Result", (), {"output": RequirementReview()})()

    monkeypatch.setattr("v2.adapters.models.Agent", QuickAgent)
    model = _stage_model(_configured_budgets())
    out = await model.generate(schema=RequirementReview, prompt="p", payload={},
                               envelope=_envelope())
    assert out == RequirementReview()
    assert state["clock"]["value"] == 5.25
    assert model.last_failures == []

@pytest.mark.anyio
async def test_a_requirement_review_that_runs_out_of_route_budget_stops(
        monkeypatch):
    state = _budgeted_clock(monkeypatch, ATTEMPT_BUDGET_S)
    model = _stage_model(_configured_budgets())
    with pytest.raises(RuntimeError,
                       match="all structured-output providers failed"):
        await model.generate(schema=RequirementReview, prompt="p", payload={},
                             envelope=_envelope())
    assert state["calls"] == ["primary", "primary"]
    assert state["clock"]["value"] == ROUTE_BUDGET_S
    assert [(failure["output_strategy"], failure["message_class"])
            for failure in model.last_failures] == [
                ("strict_schema", "timeout"), ("tool_call", "timeout"),
                ("prompted_json", "requirement_review_deadline")]

@pytest.mark.anyio
async def test_a_fast_requirement_review_failure_walks_every_rung(
        monkeypatch):
    state = _budgeted_clock(monkeypatch, 0.25)
    model = _stage_model(_configured_budgets())
    with pytest.raises(RuntimeError,
                       match="all structured-output providers failed"):
        await model.generate(schema=RequirementReview, prompt="p", payload={},
                             envelope=_envelope())
    assert state["clock"]["value"] == 0.75
    assert [(failure["output_strategy"], failure["message_class"])
            for failure in model.last_failures] == [
                ("strict_schema", "timeout"), ("tool_call", "timeout"),
                ("prompted_json", "timeout")]
