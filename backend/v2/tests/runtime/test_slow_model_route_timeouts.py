from __future__ import annotations

from contextlib import contextmanager

import pytest

from v2.adapters.models import ProviderStructuredModel
from v2.contracts import TaskSpec
from v2.runtime import RequestEnvelope


def _envelope() -> RequestEnvelope:
    return RequestEnvelope.freeze(
        provider="inception", model="primary", route="intake",
        prompt="p", context={}, tool_schemas={}, planner_version="v2")


class _Model:
    def __init__(self, name: str):
        self.model_name = name
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


@pytest.mark.anyio
async def test_intake_slow_model_completes_within_attempt_timeout(monkeypatch):
    clock = type("Clock", (), {"value": 0.0})()

    @contextmanager
    def fail_after(timeout):
        start = clock.value
        yield
        if clock.value - start > timeout:
            raise TimeoutError("attempt timed out")

    class Agent:
        def __init__(self, *args, **kwargs): pass
        async def run(self, prompt):
            clock.value += 10.0
            return type("Result", (), {"output": TaskSpec(
                goal="ok", mode="quick", deliverable="x")})()

    async def no_sleep(value): return None
    monkeypatch.setattr("v2.adapters.models.Agent", Agent)
    monkeypatch.setattr("v2.adapters.models.anyio.fail_after", fail_after)
    monkeypatch.setattr("v2.adapters.models.anyio.sleep", no_sleep)
    monkeypatch.setattr("v2.adapters.models.time.monotonic", lambda: clock.value)
    model = ProviderStructuredModel("inception", "primary")
    monkeypatch.setattr(model, "_models", lambda: [("inception", _Model("primary"))])
    out = await model.generate(
        schema=TaskSpec, prompt="p", payload={}, envelope=_envelope())
    assert isinstance(out, TaskSpec)
    assert model.last_failures == []
