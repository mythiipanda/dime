from __future__ import annotations

from contextlib import contextmanager

import pytest

from v2.adapters.models import ModelIntake, ProviderStructuredModel, ROUTE_POLICIES
from v2.adapters.structured import EndpointCapabilities, resolve_strategy
from v2.contracts import RequirementReview, TaskSpec
from v2.runtime import RequestEnvelope


def _envelope() -> RequestEnvelope:
    return RequestEnvelope.freeze(
        provider="inception", model="primary", route="requirement_review",
        prompt="p", context={}, tool_schemas={}, planner_version="v2")


class _Model:
    def __init__(self, name: str):
        self.model_name = name
        self.capabilities = EndpointCapabilities(
            endpoint="https://stub.invalid/v1", strict_json_schema=True,
            tool_calling=True, strict_tool_definitions=True)
        self.strategy = resolve_strategy(self.capabilities)


def test_requirement_review_policy_changes_only_attempt_timeout():
    expected = {
        "intake": {"max_attempts": 2, "attempt_timeout_s": 30.0,
            "total_budget_s": 60.0},
        "requirement_review": {"max_attempts": 2, "attempt_timeout_s": 30.0,
            "total_budget_s": 60.0},
        "planner": {"max_attempts": 2, "attempt_timeout_s": 30.0,
            "total_budget_s": 60.0},
        "synthesizer": {"max_attempts": 2, "attempt_timeout_s": 25.0,
            "total_budget_s": 50.0},
        "semantic_verifier": {"max_attempts": 2, "attempt_timeout_s": 30.0,
            "total_budget_s": 60.0},
    }
    assert ROUTE_POLICIES == expected


@pytest.mark.anyio
async def test_requirement_review_response_after_four_before_eight_completes(monkeypatch):
    clock = type("Clock", (), {"value": 0.0})(); timeouts = []
    @contextmanager
    def fail_after(timeout):
        timeouts.append(timeout); yield
    class Agent:
        def __init__(self, *args, **kwargs): pass
        async def run(self, prompt):
            clock.value += 5.25
            return type("Result", (), {"output": RequirementReview()})()
    monkeypatch.setattr("v2.adapters.models.Agent", Agent)
    monkeypatch.setattr("v2.adapters.models.anyio.fail_after", fail_after)
    monkeypatch.setattr("v2.adapters.models.time.monotonic", lambda: clock.value)
    model = ProviderStructuredModel("inception", "primary")
    monkeypatch.setattr(model, "_models", lambda: [("inception", _Model("primary"))])
    out = await model.generate(schema=RequirementReview, prompt="p", payload={}, envelope=_envelope())
    assert out == RequirementReview() and timeouts == [30.0]
    assert model.last_failures == []


@pytest.mark.anyio
async def test_requirement_review_remaining_budget_caps_attempt_two_and_blocks_secondary(monkeypatch):
    clock = type("Clock", (), {"value": 0.0})(); timeouts = []; agents = []; current = []
    @contextmanager
    def fail_after(timeout):
        timeouts.append(timeout); current.append(timeout)
        try: yield
        finally: current.pop()
    class Agent:
        def __init__(self, model, *args, **kwargs): agents.append(model.model_name)
        async def run(self, prompt):
            clock.value += current[-1]; raise TimeoutError("bounded")
    async def no_sleep(value): return None
    monkeypatch.setattr("v2.adapters.models.Agent", Agent)
    monkeypatch.setattr("v2.adapters.models.anyio.fail_after", fail_after)
    monkeypatch.setattr("v2.adapters.models.anyio.sleep", no_sleep)
    monkeypatch.setattr("v2.adapters.models.random.uniform", lambda a, b: 0)
    monkeypatch.setattr("v2.adapters.models.time.monotonic", lambda: clock.value)
    monkeypatch.setattr("v2.adapters.models.time.perf_counter", lambda: clock.value)
    model = ProviderStructuredModel("inception", "primary")
    monkeypatch.setattr(model, "_models", lambda: [("inception", _Model("primary")), ("mistral", _Model("secondary"))])
    with pytest.raises(RuntimeError, match="all structured-output providers failed"):
        await model.generate(schema=RequirementReview, prompt="p", payload={}, envelope=_envelope())
    assert timeouts == [30.0, 30.0] and agents == ["primary", "primary"]
    assert clock.value == 60.0


@pytest.mark.anyio
async def test_fast_primary_failures_raise_without_secondary_within_budget(monkeypatch):
    clock = type("Clock", (), {"value": 0.0})(); calls = []; timeouts = []
    @contextmanager
    def fail_after(timeout):
        timeouts.append(timeout); yield
    class Agent:
        def __init__(self, model, *args, **kwargs): self.name = model.model_name
        async def run(self, prompt):
            calls.append(self.name); clock.value += 0.25
            raise TimeoutError("fast transient")
    async def no_sleep(value): return None
    monkeypatch.setattr("v2.adapters.models.Agent", Agent)
    monkeypatch.setattr("v2.adapters.models.anyio.fail_after", fail_after)
    monkeypatch.setattr("v2.adapters.models.anyio.sleep", no_sleep)
    monkeypatch.setattr("v2.adapters.models.random.uniform", lambda a, b: 0)
    monkeypatch.setattr("v2.adapters.models.time.monotonic", lambda: clock.value)
    model = ProviderStructuredModel("inception", "primary")
    monkeypatch.setattr(model, "_models", lambda: [("inception", _Model("primary")), ("mistral", _Model("secondary"))])
    with pytest.raises(RuntimeError, match="all structured-output providers failed"):
        await model.generate(schema=RequirementReview, prompt="p", payload={}, envelope=_envelope())
    assert calls == ["primary", "primary"]
    assert timeouts == [30.0, 30.0] and clock.value == 0.5
    assert len(model.last_failures) == 2
