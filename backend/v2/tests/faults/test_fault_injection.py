from __future__ import annotations

import asyncio
from datetime import datetime

import pytest
from pydantic import ValidationError

from v2.contracts import ClaimResult, EvidenceEnvelope, VerificationReport, VerificationStatus
from v2.tests.faults.injection import (
    FaultInjector,
    InjectedTimeout,
    InjectedToolFailure,
    MemoryCheckpoint,
    run_nodes,
)


def run(coro):
    return asyncio.run(coro)


def test_planner_timeout_is_not_swallowed():
    injector = FaultInjector()
    injector.inject("planner", InjectedTimeout("planner timed out"))
    with pytest.raises(InjectedTimeout, match="planner timed out"):
        run(injector.call("planner", lambda: asyncio.sleep(0)))


def test_provider_timeout_is_not_swallowed():
    injector = FaultInjector()
    injector.inject("provider", InjectedTimeout("provider timed out"))
    with pytest.raises(InjectedTimeout, match="provider timed out"):
        run(injector.call("provider", lambda: asyncio.sleep(0)))


def test_tool_failure_consumes_only_injected_attempt():
    injector = FaultInjector()
    injector.inject("tool:ratings", InjectedToolFailure("warehouse unavailable"))
    checkpoint = MemoryCheckpoint()
    async def execute(node_id):
        return {"node": node_id}
    with pytest.raises(InjectedToolFailure):
        run(run_nodes(["ratings"], checkpoint, injector, execute))
    run(run_nodes(["ratings"], checkpoint, injector, execute))
    assert checkpoint.completed == {"ratings"}


def test_malformed_evidence_is_rejected_at_contract_wall():
    with pytest.raises(ValidationError):
        EvidenceEnvelope(
            evidence_id="bad", capability="ratings", source="fixture",
            observed_at="not-a-date", rows=None,
        )


def test_contradictory_evidence_can_be_preserved_for_verifier():
    first = EvidenceEnvelope(
        evidence_id="a", capability="standings", source="one",
        observed_at=datetime(2026, 9, 14), rows={"wins": 54},
    )
    second = first.model_copy(update={"evidence_id": "b", "source": "two", "rows": {"wins": 55}})
    report = VerificationReport(
        status=VerificationStatus.REPAIR,
        claim_results=[ClaimResult(claim_index=0, supported=False, reasons=["contradictory wins"])],
        contradictions=[f"{first.evidence_id} and {second.evidence_id} disagree"],
        repair_instructions=["resolve source precedence"],
    )
    assert report.status == VerificationStatus.REPAIR
    assert report.contradictions


def test_checkpoint_restart_skips_completed_nodes():
    checkpoint = MemoryCheckpoint(completed={"a"}, evidence={"a": 1})
    injector = FaultInjector()
    called = []
    async def execute(node_id):
        called.append(node_id)
        return len(called)
    run(run_nodes(["a", "b", "c"], checkpoint, injector, execute))
    assert called == ["b", "c"]
    assert checkpoint.completed == {"a", "b", "c"}


def test_verifier_rejection_is_a_repair_not_publish_signal():
    report = VerificationReport(
        status=VerificationStatus.REPAIR,
        claim_results=[ClaimResult(claim_index=0, supported=False, reasons=["uncited numeral"])],
        repair_instructions=["cite evidence or remove claim"],
    )
    assert report.status != VerificationStatus.PASS


def test_cancellation_stops_before_next_checkpoint():
    checkpoint = MemoryCheckpoint()
    injector = FaultInjector()
    started = asyncio.Event()
    async def execute(node_id):
        started.set()
        await asyncio.sleep(60)
    async def scenario():
        task = asyncio.create_task(run_nodes(["a", "b"], checkpoint, injector, execute))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    run(scenario())
    assert checkpoint.completed == set()


@pytest.mark.anyio
async def test_executor_does_not_admit_wrong_season_evidence():
    from v2.contracts import Plan, PlanNode, RunMode, SeasonRef, TaskSpec
    from v2.runtime.executor import PlanExecutor
    from v2.runtime.fakes import FakeCapability

    task = TaskSpec(
        goal="2025-26 trade", mode=RunMode.QUICK, deliverable="answer",
        season=SeasonRef(value="2025-26", source="user", confidence=1))
    plan = Plan(nodes=[PlanNode(
        id="salary", description="salary", capability_hints=["contracts"])])
    capability = FakeCapability("contracts", {"salary": 3876529})

    result = await PlanExecutor({"contracts": capability}).execute(task, plan)
    assert result.evidence[0].season == "2025-26"
