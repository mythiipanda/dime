from __future__ import annotations

import asyncio
import time

import pytest
from v2.contracts import Plan, PlanNode, RunMode, TaskSpec
from v2.runtime import FakeCapability, PlanExecutor, Runtime
from v2.runtime.ledger import LedgerKind, RunLedger, TerminalReason


@pytest.fixture
def anyio_backend():
    return "asyncio"


class SlowCapability(FakeCapability):
    async def execute(self, node, task, evidence):
        await asyncio.sleep(30)
        return await super().execute(node, task, evidence)


class Intake:
    async def understand(self, request: str) -> TaskSpec:
        return TaskSpec(goal=request, mode=RunMode.QUICK, deliverable="text")


class Planner:
    def __init__(self, hints: list[str]) -> None:
        self._hints = hints

    async def plan(self, task: TaskSpec) -> Plan:
        return Plan(
            nodes=[
                PlanNode(
                    id=f"node-{index}",
                    description=f"node-{index}",
                    capability_hints=[hint],
                )
                for index, hint in enumerate(self._hints)
            ]
        )


class Unreached:
    async def __call__(self, *args, **kwargs):
        raise AssertionError("stage must not run after budget timeout")

    async def understand(self, *args, **kwargs):
        raise AssertionError("stage must not run after budget timeout")

    async def plan(self, *args, **kwargs):
        raise AssertionError("stage must not run after budget timeout")

    async def synthesize(self, *args, **kwargs):
        raise AssertionError("stage must not run after budget timeout")

    async def verify(self, *args, **kwargs):
        raise AssertionError("stage must not run after budget timeout")


def budget_task() -> TaskSpec:
    return TaskSpec(goal="budget probe", mode=RunMode.QUICK, deliverable="text")


@pytest.mark.anyio
async def test_slow_node_fails_fast_while_sibling_completes():
    executor = PlanExecutor(
        {"slow": SlowCapability("slow", {"value": 1}),
         "fast": FakeCapability("fast", {"value": 2})},
        node_timeout_s=0.2)
    plan = Plan(
        nodes=[
            PlanNode(id="slow", description="slow",
                     capability_hints=["slow"]),
            PlanNode(id="fast", description="fast",
                     capability_hints=["fast"]),
        ]
    )
    started = time.monotonic()
    result = await executor.execute(budget_task(), plan)
    elapsed = time.monotonic() - started
    by_id = {node.id: node for node in result.plan.nodes}
    assert by_id["slow"].status.value == "failed"
    assert by_id["fast"].status.value == "complete"
    assert result.errors["slow"] == ["node slow timed out after 0.2s"]
    assert result.evidence_by_node["fast"].rows == {"value": 2}
    assert elapsed < 10


@pytest.mark.anyio
async def test_run_level_timeout_stops_hung_execute():
    ledger = RunLedger("probe")
    runtime = Runtime(
        intake=Intake(),
        planner=Planner(["slow"]),
        executor=PlanExecutor({"slow": SlowCapability("slow", {"value": 1})}),
        synthesizer=Unreached(),
        mechanical_verifier=Unreached(),
        semantic_verifier=Unreached(),
        ledger=ledger,
        run_timeout_s=0.3,
    )
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await runtime.run("probe", run_id="probe")
    elapsed = time.monotonic() - started
    assert elapsed < 10
    turn_ends = [entry for entry in ledger.entries
                 if entry.kind == LedgerKind.TURN_END]
    assert turn_ends
    assert turn_ends[-1].data["reason"] == TerminalReason.TIMEOUT.value
