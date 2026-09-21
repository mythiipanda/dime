from __future__ import annotations

from contextlib import contextmanager

import pytest

from v2.adapters.models import ModelIntake, ProviderStructuredModel, ROUTE_POLICIES
from v2.contracts import RequirementReview, TaskSpec
from v2.runtime import RequestEnvelope


def _envelope() -> RequestEnvelope:
    return RequestEnvelope.freeze(
        provider="inception", model="primary", route="requirement_review",
        prompt="p", context={}, tool_schemas={}, planner_version="v2")


class _Model:
    def __init__(self, name: str):
        self.model_name = name


def test_requirement_review_policy_changes_only_attempt_timeout():
    expected = {
        "intake": {"primary_attempts": 2, "attempt_timeout_s": 6.0,
            "total_budget_s": 18.0, "secondary_limit": 1,
            "transient_classes": frozenset({"timeout", "rate_limit", "network", "server_error", "provider_error"}),
            "deterministic_fallback": False},
        "intake_admission": {"primary_attempts": 1, "attempt_timeout_s": 6.0,
            "total_budget_s": 6.0, "secondary_limit": 0,
            "transient_classes": frozenset(), "deterministic_fallback": False},
        "requirement_review": {"primary_attempts": 2, "attempt_timeout_s": 8.0,
            "total_budget_s": 12.0, "secondary_limit": 1,
            "transient_classes": frozenset({"timeout", "rate_limit", "network", "server_error", "provider_error"}),
            "deterministic_fallback": True},
        "planner": {"primary_attempts": 2, "attempt_timeout_s": 4.0,
            "total_budget_s": 12.0, "secondary_limit": 1,
            "transient_classes": frozenset({"timeout", "rate_limit", "network", "server_error", "provider_error"}),
            "deterministic_fallback": False},
        "synthesizer": {"primary_attempts": 1, "attempt_timeout_s": 6.0,
            "total_budget_s": 6.0, "secondary_limit": 0,
            "transient_classes": frozenset(), "deterministic_fallback": True},
        "semantic_verifier": {"primary_attempts": 1, "attempt_timeout_s": 6.0,
            "total_budget_s": 6.0, "secondary_limit": 0,
            "transient_classes": frozenset(), "deterministic_fallback": True},
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
    assert out == RequirementReview() and timeouts == [8.0]
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
    with pytest.raises(RuntimeError, match="requirement_review_deadline"):
        await model.generate(schema=RequirementReview, prompt="p", payload={}, envelope=_envelope())
    assert timeouts == [8.0, 4.0] and agents == ["primary", "primary"]
    assert clock.value == 12.0


@pytest.mark.anyio
async def test_fast_primary_failures_still_allow_secondary_within_budget(monkeypatch):
    clock = type("Clock", (), {"value": 0.0})(); calls = []; timeouts = []
    @contextmanager
    def fail_after(timeout):
        timeouts.append(timeout); yield
    class Agent:
        def __init__(self, model, *args, **kwargs): self.name = model.model_name
        async def run(self, prompt):
            calls.append(self.name); clock.value += 0.25
            if self.name == "primary": raise TimeoutError("fast transient")
            return type("Result", (), {"output": RequirementReview()})()
    async def no_sleep(value): return None
    monkeypatch.setattr("v2.adapters.models.Agent", Agent)
    monkeypatch.setattr("v2.adapters.models.anyio.fail_after", fail_after)
    monkeypatch.setattr("v2.adapters.models.anyio.sleep", no_sleep)
    monkeypatch.setattr("v2.adapters.models.random.uniform", lambda a, b: 0)
    monkeypatch.setattr("v2.adapters.models.time.monotonic", lambda: clock.value)
    model = ProviderStructuredModel("inception", "primary")
    monkeypatch.setattr(model, "_models", lambda: [("inception", _Model("primary")), ("mistral", _Model("secondary"))])
    out = await model.generate(schema=RequirementReview, prompt="p", payload={}, envelope=_envelope())
    assert out == RequirementReview()
    assert calls == ["primary", "primary", "secondary"]
    assert timeouts == [8.0, 8.0, 8.0] and clock.value == 0.75
    assert len(model.last_failures) == 2


@pytest.mark.anyio
async def test_total_review_outage_materializes_existing_typed_fallback():
    class Outage:
        async def generate(self, **call):
            raise RuntimeError("all structured-output providers failed [timeout]")

    task = TaskSpec(goal="lowest pace", mode="quick", deliverable="team",
        season={"value":"2025-26", "source":"user", "confidence":1},
        required_evidence=["team_ratings"])
    review = await ModelIntake(Outage(), provider="stub", model_name="stub",
        capability_catalog={"team_ratings": {}}, requirement_review=True,
    )._review_requirements("Which team has the lowest pace?", task)
    assert len(review.requirements) == 1
    assert review.requirements[0].capability_arguments == {
        "season":"2025-26", "requested_metric":"PACE", "ranking_direction":"asc"}
