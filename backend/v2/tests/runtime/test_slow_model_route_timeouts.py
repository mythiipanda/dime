from __future__ import annotations

import json
from contextlib import contextmanager

import httpx
import pytest
from pydantic_ai.providers.openai import OpenAIProvider

from v2.adapters.models import (
    MODEL_BUDGETS_PATH,
    DimeOpenAIChatModel,
    ModelBudgets,
    ProviderStructuredModel,
    ReasoningContentFallbackClient,
    RoutePolicy,
    load_model_budgets,
    route_budgets,
)
from v2.adapters.structured import (
    CapabilityMeasurement,
    EndpointCapabilities,
    Support,
)
from v2.contracts import TaskSpec
from v2.runtime import RequestEnvelope

SLOW_STAGE_SECONDS = 45.0
CAPABILITIES = EndpointCapabilities(
    endpoint="https://stub.invalid/v1", strict_json_schema=Support.MEASURED,
    tool_calling=Support.MEASURED, strict_tool_definitions=Support.MEASURED,
    measurement=CapabilityMeasurement(
        probe="stub", measured_at="2026-10-05", models=("primary",)))

def _envelope(route: str = "intake") -> RequestEnvelope:
    return RequestEnvelope.freeze(
        provider="inception", model="primary", route=route,
        prompt="p", context={}, tool_schemas={}, planner_version="v2")

def _stage_model(budgets: ModelBudgets | None = None) -> ProviderStructuredModel:
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(500, json={"error": {"message": "x"}})))
    chat_model = DimeOpenAIChatModel(
        "primary",
        provider=OpenAIProvider(openai_client=ReasoningContentFallbackClient(
            api_key="stub", max_retries=0, http_client=client)),
        capabilities=CAPABILITIES)
    model = ProviderStructuredModel("inception", "primary", model_budgets=budgets)
    model._models = lambda: [("inception", chat_model)]
    return model

def _slow_agent(monkeypatch, seconds: float, *, fails: bool = False) -> list[float]:
    clock = type("Clock", (), {"value": 0.0})()
    spent: list[float] = []

    @contextmanager
    def fail_after(timeout):
        started = clock.value
        yield
        if clock.value - started > timeout:
            raise TimeoutError("attempt timed out")

    class Agent:
        def __init__(self, *args, **kwargs): pass
        async def run(self, prompt):
            spent.append(seconds)
            clock.value += seconds
            if fails:
                raise RuntimeError("500 Internal Server Error")
            return type("Result", (), {"output": TaskSpec(
                goal="ok", mode="quick", deliverable="x")})()

    async def no_sleep(value): return None
    monkeypatch.setattr("v2.adapters.models.Agent", Agent)
    monkeypatch.setattr("v2.adapters.models.anyio.fail_after", fail_after)
    monkeypatch.setattr("v2.adapters.models.anyio.sleep", no_sleep)
    monkeypatch.setattr("v2.adapters.models.random.uniform", lambda a, b: 0)
    monkeypatch.setattr("v2.adapters.models.time.monotonic", lambda: clock.value)
    monkeypatch.setattr(
        "v2.adapters.models.time.perf_counter", lambda: clock.value)
    return spent

def test_the_shipped_budgets_impose_no_deadline_on_a_stage_call():
    budgets = load_model_budgets()
    assert MODEL_BUDGETS_PATH.exists()
    assert budgets.transport_timeout_s >= 600.0
    for route in ("intake", "requirement_review", "planner", "synthesizer",
                  "semantic_verifier", "repair"):
        policy = route_budgets(budgets, route)
        assert policy.attempt_timeout_s is None, route
        assert policy.total_budget_s is None, route
    assert budgets == ModelBudgets(transport_timeout_s=600.0,
                                   defaults=RoutePolicy(), routes={})

def test_a_configured_budget_is_read_per_route_and_may_be_very_large(tmp_path):
    path = tmp_path / "budgets.json"
    path.write_text(json.dumps({
        "transport_timeout_s": 900.0,
        "default": {"attempt_timeout_s": 1200.0},
        "routes": {"intake": {"attempt_timeout_s": 60.0,
                              "total_budget_s": 3600.0}}}))
    budgets = load_model_budgets(path)
    assert budgets.transport_timeout_s == 900.0
    assert route_budgets(budgets, "intake") == RoutePolicy(
        attempt_timeout_s=60.0, total_budget_s=3600.0)
    assert route_budgets(budgets, "planner") == RoutePolicy(
        attempt_timeout_s=1200.0)
    assert route_budgets(budgets, "unknown_route") == RoutePolicy(
        attempt_timeout_s=1200.0)

@pytest.mark.parametrize("document", [
    {"transport_timeout_s": 0, "default": {}, "routes": {}},
    {"default": {}, "routes": {}},
    {"transport_timeout_s": 60.0, "default": {"attempt_timeout_s": 0},
     "routes": {}},
    {"transport_timeout_s": 60.0, "default": {"total_budget_s": -1.0},
     "routes": {}},
    {"transport_timeout_s": 60.0, "default": {"attempt_timeout_s": "60"},
     "routes": {}},
    {"transport_timeout_s": 60.0, "default": {}, "routes": {"intake": []}},
    {"transport_timeout_s": 60.0, "default": {}, "routes": {"intake": {
        "unknown_key": 1}}},
])
def test_a_malformed_budget_document_fails_loudly(tmp_path, document):
    path = tmp_path / "budgets.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        load_model_budgets(path)

@pytest.mark.anyio
async def test_a_forty_five_second_stage_survives_the_default_budget(monkeypatch):
    spent = _slow_agent(monkeypatch, SLOW_STAGE_SECONDS)
    model = _stage_model()
    out = await model.generate(
        schema=TaskSpec, prompt="p", payload={}, envelope=_envelope())
    assert isinstance(out, TaskSpec)
    assert spent == [SLOW_STAGE_SECONDS]
    assert model.last_failures == []
    assert str(model.last_output_strategy) == "strict_schema"

@pytest.mark.anyio
async def test_a_configured_attempt_budget_kills_the_same_slow_stage(monkeypatch):
    spent = _slow_agent(monkeypatch, SLOW_STAGE_SECONDS)
    budgets = ModelBudgets(
        transport_timeout_s=600.0, defaults=RoutePolicy(attempt_timeout_s=5.0),
        routes={})
    model = _stage_model(budgets)
    with pytest.raises(RuntimeError,
                       match="all structured-output providers failed"):
        await model.generate(schema=TaskSpec, prompt="p", payload={},
                             envelope=_envelope())
    assert spent == [SLOW_STAGE_SECONDS] * 3
    assert [failure["message_class"]
            for failure in model.last_failures] == ["timeout"] * 3
    assert [failure["output_strategy"]
            for failure in model.last_failures] == [
                "strict_schema", "tool_call", "prompted_json"]

@pytest.mark.anyio
async def test_the_run_deadline_bounds_a_stage_the_budgets_do_not(monkeypatch):
    from v2.runtime.budget import RUN_MODEL_DEADLINE
    _slow_agent(monkeypatch, SLOW_STAGE_SECONDS, fails=True)
    RUN_MODEL_DEADLINE.set(10.0)
    try:
        model = _stage_model()
        with pytest.raises(RuntimeError,
                           match="all structured-output providers failed"):
            await model.generate(schema=TaskSpec, prompt="p", payload={},
                                 envelope=_envelope())
        assert [(failure["message_class"], failure["output_strategy"])
                for failure in model.last_failures] == [
                    ("server_error", "strict_schema"),
                    ("intake_deadline", "tool_call")]
    finally:
        RUN_MODEL_DEADLINE.set(None)
