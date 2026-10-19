from __future__ import annotations

import asyncio
import importlib
import time

import pytest
from v2.contracts import Plan, PlanNode, RunMode, TaskSpec
from v2.runtime import FakeCapability, PlanExecutor, Runtime
from v2.runtime.ledger import LedgerKind, RunLedger, TerminalReason
from v2.runtime.loop import PreToolTimeoutError, RunTimeoutError

importlib.import_module("v2.adapters.models")

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

class HungIntake:
    async def understand(self, request: str) -> TaskSpec:
        await asyncio.sleep(30)
        return budget_task()

class HungPlanner:
    async def plan(self, task: TaskSpec) -> Plan:
        await asyncio.sleep(30)
        return Plan(nodes=[])

def hung_runtime(*, intake, planner, run_timeout_s=None,
                 pre_tool_timeout_s=None):
    ledger = RunLedger("probe")
    runtime = Runtime(
        intake=intake,
        planner=planner,
        executor=PlanExecutor({"slow": SlowCapability("slow", {"value": 1})}),
        synthesizer=Unreached(),
        mechanical_verifier=Unreached(),
        semantic_verifier=Unreached(),
        ledger=ledger,
        run_timeout_s=run_timeout_s,
        pre_tool_timeout_s=pre_tool_timeout_s,
    )
    return runtime, ledger

def terminal_reasons(ledger):
    return [entry.data["reason"] for entry in ledger.entries
            if entry.kind in {LedgerKind.STEP_END, LedgerKind.TURN_END}]

async def run_with_watchdog(runtime, watchdog=1.0):
    return await asyncio.wait_for(runtime.run("probe", run_id="probe"),
                                  timeout=watchdog)

@pytest.mark.anyio
async def test_run_budget_bounds_hung_intake_without_pre_tool_budget():
    runtime, ledger = hung_runtime(
        intake=HungIntake(), planner=Planner([]), run_timeout_s=0.05)
    started = time.monotonic()
    with pytest.raises(RunTimeoutError):
        await run_with_watchdog(runtime)
    assert time.monotonic() - started < 1.0
    assert terminal_reasons(ledger)[-1] == TerminalReason.TIMEOUT.value

@pytest.mark.anyio
async def test_run_budget_bounds_hung_planner_without_pre_tool_budget():
    runtime, ledger = hung_runtime(
        intake=Intake(), planner=HungPlanner(), run_timeout_s=0.05)
    started = time.monotonic()
    with pytest.raises(RunTimeoutError):
        await run_with_watchdog(runtime)
    assert time.monotonic() - started < 1.0
    assert terminal_reasons(ledger)[-1] == TerminalReason.TIMEOUT.value

@pytest.mark.anyio
async def test_pre_tool_budget_bounds_hung_intake_without_run_budget():
    runtime, ledger = hung_runtime(
        intake=HungIntake(), planner=Planner([]), pre_tool_timeout_s=0.05)
    started = time.monotonic()
    with pytest.raises(PreToolTimeoutError):
        await run_with_watchdog(runtime)
    assert time.monotonic() - started < 1.0
    assert terminal_reasons(ledger)[-1] == TerminalReason.TIMEOUT.value

@pytest.mark.anyio
async def test_pre_tool_budget_bounds_hung_planner_without_run_budget():
    runtime, ledger = hung_runtime(
        intake=Intake(), planner=HungPlanner(), pre_tool_timeout_s=0.05)
    started = time.monotonic()
    with pytest.raises(PreToolTimeoutError):
        await run_with_watchdog(runtime)
    assert time.monotonic() - started < 1.0
    assert terminal_reasons(ledger)[-1] == TerminalReason.TIMEOUT.value

@pytest.mark.anyio
async def test_run_budget_first_reports_run_timeout():
    runtime, _ledger = hung_runtime(
        intake=HungIntake(), planner=Planner([]),
        run_timeout_s=0.05, pre_tool_timeout_s=5.0)
    with pytest.raises(RunTimeoutError):
        await run_with_watchdog(runtime)

@pytest.mark.anyio
async def test_pre_tool_budget_first_reports_pre_tool_timeout():
    runtime, _ledger = hung_runtime(
        intake=HungIntake(), planner=Planner([]),
        run_timeout_s=5.0, pre_tool_timeout_s=0.05)
    with pytest.raises(PreToolTimeoutError):
        await run_with_watchdog(runtime)

@pytest.mark.anyio
async def test_no_budget_leaves_intake_unbounded():
    runtime, _ledger = hung_runtime(intake=HungIntake(), planner=Planner([]))
    with pytest.raises(asyncio.TimeoutError) as excinfo:
        await run_with_watchdog(runtime, watchdog=0.5)
    assert not isinstance(excinfo.value, (RunTimeoutError, PreToolTimeoutError))

class SlowCompletingIntake:
    def __init__(self, delay: float) -> None:
        self._delay = delay

    async def understand(self, request: str) -> TaskSpec:
        await asyncio.sleep(self._delay)
        return budget_task()

def step_end(ledger, step_id):
    return [entry for entry in ledger.entries
            if entry.kind == LedgerKind.STEP_END
            and entry.step_id == step_id][-1]

@pytest.mark.anyio
async def test_run_budget_is_cumulative_across_intake_and_planning():
    runtime, ledger = hung_runtime(
        intake=SlowCompletingIntake(0.7), planner=HungPlanner(),
        run_timeout_s=1.0)
    started = time.monotonic()
    with pytest.raises(RunTimeoutError):
        await run_with_watchdog(runtime, watchdog=5.0)
    elapsed = time.monotonic() - started
    understand = step_end(ledger, "understand")
    plan = step_end(ledger, "plan")
    assert understand.data["reason"] == TerminalReason.COMPLETE.value
    assert plan.data["reason"] == TerminalReason.TIMEOUT.value
    assert 550 <= understand.data["duration_ms"] < 950
    assert plan.data["duration_ms"] < 800
    assert elapsed < 1.35

@pytest.mark.anyio
async def test_pre_tool_budget_is_cumulative_across_intake_and_planning():
    runtime, ledger = hung_runtime(
        intake=SlowCompletingIntake(0.7), planner=HungPlanner(),
        pre_tool_timeout_s=1.0)
    started = time.monotonic()
    with pytest.raises(PreToolTimeoutError):
        await run_with_watchdog(runtime, watchdog=5.0)
    elapsed = time.monotonic() - started
    understand = step_end(ledger, "understand")
    plan = step_end(ledger, "plan")
    assert understand.data["reason"] == TerminalReason.COMPLETE.value
    assert plan.data["reason"] == TerminalReason.TIMEOUT.value
    assert 550 <= understand.data["duration_ms"] < 950
    assert plan.data["duration_ms"] < 800
    assert elapsed < 1.35
