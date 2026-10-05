import time

import anyio
import pytest

from v2.adapters.models import ROUTE_POLICIES, ProviderStructuredModel
from v2.contracts import TaskSpec
from v2.runtime import RequestEnvelope


def _planner_envelope():
    return RequestEnvelope.freeze(
        provider="inception", model="primary", route="planner",
        prompt="p", context={}, tool_schemas={}, planner_version="v2")


class _Model:
    model_name = "primary"
    @property
    def strategy(self):
        from v2.adapters.structured import (EndpointCapabilities,
                                            resolve_strategy)
        return resolve_strategy(self.capabilities)

    @property
    def capabilities(self):
        from v2.adapters.structured import EndpointCapabilities
        return EndpointCapabilities(
            endpoint="https://stub.invalid/v1", strict_json_schema=True,
            tool_calling=True, strict_tool_definitions=True)


def _ok_result():
    return type("R", (), {
        "output": TaskSpec(goal="ok", mode="quick", deliverable="x")})()


@pytest.mark.anyio
async def test_never_tokens_hang_is_bounded(monkeypatch):
    policy = ROUTE_POLICIES["planner"]

    class HangingAgent:
        def __init__(self, *a, **k):
            pass

        async def run(self, prompt):
            await anyio.sleep_forever()

    monkeypatch.setattr("v2.adapters.models.Agent", HangingAgent)
    m = ProviderStructuredModel("inception", "primary")
    monkeypatch.setattr(m, "_models", lambda: [("inception", _Model())])
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="all structured-output providers failed"):
        await m.generate(schema=TaskSpec, prompt="p",
                         payload={"q": "x"}, envelope=_planner_envelope())
    elapsed = time.monotonic() - started
    budget = policy["total_budget_s"]
    assert elapsed >= budget - 0.5, f"hung call returned too fast ({elapsed:.2f}s)"
    assert elapsed <= budget + 5.0, f"hung call exceeded bound ({elapsed:.2f}s)"
    assert [f["message_class"] for f in m.last_failures] == ["timeout"] * policy["max_attempts"]
    print(f"\nnever-tokens planner hang resolved in {elapsed:.2f}s "
          f"(bound: {policy['max_attempts']}x{policy['attempt_timeout_s']}s budget {budget:.1f}s)")


@pytest.mark.anyio
async def test_slow_dribble_hang_is_bounded(monkeypatch):
    policy = ROUTE_POLICIES["planner"]

    class DribblingAgent:
        def __init__(self, *a, **k):
            pass

        async def run(self, prompt):
            for _ in range(1000):
                await anyio.sleep(0.2)

    monkeypatch.setattr("v2.adapters.models.Agent", DribblingAgent)
    m = ProviderStructuredModel("inception", "primary")
    monkeypatch.setattr(m, "_models", lambda: [("inception", _Model())])
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="all structured-output providers failed"):
        await m.generate(schema=TaskSpec, prompt="p",
                         payload={"q": "x"}, envelope=_planner_envelope())
    elapsed = time.monotonic() - started
    budget = policy["total_budget_s"]
    assert elapsed >= budget - 0.5, f"dribble returned too fast ({elapsed:.2f}s)"
    assert elapsed <= budget + 5.0, f"dribble exceeded bound ({elapsed:.2f}s)"
    assert [f["message_class"] for f in m.last_failures] == ["timeout"] * policy["max_attempts"]
    print(f"\nslow-dribble planner hang resolved in {elapsed:.2f}s "
          f"(bound: {policy['max_attempts']}x{policy['attempt_timeout_s']}s budget {budget:.1f}s)")


@pytest.mark.anyio
async def test_healthy_provider_unaffected(monkeypatch):
    class HealthyAgent:
        def __init__(self, *a, **k):
            pass

        async def run(self, prompt):
            return _ok_result()

    monkeypatch.setattr("v2.adapters.models.Agent", HealthyAgent)
    m = ProviderStructuredModel("inception", "primary")
    monkeypatch.setattr(m, "_models", lambda: [("inception", _Model())])
    started = time.monotonic()
    out = await m.generate(schema=TaskSpec, prompt="p",
                           payload={"q": "x"}, envelope=_planner_envelope())
    elapsed = time.monotonic() - started
    assert out.goal == "ok"
    assert elapsed < 2.0, f"healthy call slowed ({elapsed:.2f}s)"
    assert m.last_failures == []
    print(f"\nhealthy planner call resolved in {elapsed:.3f}s")
