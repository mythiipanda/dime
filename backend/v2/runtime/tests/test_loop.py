from __future__ import annotations

import pytest
from v2.contracts import (
    Claim,
    ClaimKind,
    DraftReport,
    Plan,
    PlanNode,
    RunMode,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
)
from v2.runtime import FakeCapability, PlanExecutor, Runtime

@pytest.fixture
def anyio_backend():
    return "asyncio"



class Intake:
    async def understand(self, request: str) -> TaskSpec:
        return TaskSpec(goal=request, mode=RunMode.QUICK, deliverable="text")


class Planner:
    async def plan(self, task: TaskSpec) -> Plan:
        return Plan(
            nodes=[
                PlanNode(
                    id="facts",
                    description="facts",
                    capability_hints=["fake"],
                    completion_test="has facts",
                )
            ]
        )


class Synthesizer:
    async def synthesize(self, task, evidence) -> DraftReport:
        return DraftReport(
            sections=["Answer"],
            claims=[
                Claim(
                    text="42", kind=ClaimKind.OBSERVED, evidence_ids=["evidence:facts"]
                )
            ],
        )


class SequenceVerifier:
    def __init__(self, *statuses: VerificationStatus) -> None:
        self.statuses = list(statuses)

    async def verify(self, task, draft, evidence) -> VerificationReport:
        return VerificationReport(status=self.statuses.pop(0))


class Repairer:
    async def repair(self, task, draft, evidence, verification) -> DraftReport:
        return draft.model_copy(update={"sections": ["Repaired"]})


def runtime(mechanical, semantic, repairer=None) -> Runtime:
    return Runtime(
        intake=Intake(),
        planner=Planner(),
        executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}),
        synthesizer=Synthesizer(),
        mechanical_verifier=mechanical,
        semantic_verifier=semantic,
        repairer=repairer,
    )


@pytest.mark.anyio
async def test_passes_verified_quick_slice() -> None:
    result = await runtime(
        SequenceVerifier(VerificationStatus.PASS),
        SequenceVerifier(VerificationStatus.PASS),
    ).run("answer")

    assert result.verification.status == VerificationStatus.PASS
    assert result.repaired is False


@pytest.mark.anyio
async def test_repairs_once_and_reverifies() -> None:
    result = await runtime(
        SequenceVerifier(VerificationStatus.REPAIR, VerificationStatus.PASS),
        SequenceVerifier(VerificationStatus.PASS, VerificationStatus.PASS),
        Repairer(),
    ).run("answer")

    assert result.repaired is True
    assert result.draft.sections == ["Repaired"]
    assert result.verification.status == VerificationStatus.PASS


@pytest.mark.anyio
async def test_exhausted_repair_returns_named_partial() -> None:
    class RejectingVerifier:
        async def verify(self, task, draft, evidence):
            return VerificationReport(
                status=VerificationStatus.REPAIR,
                missing_branches=["clutch context"],
                repair_instructions=["add clutch evidence"],
            )

    result = await runtime(RejectingVerifier(), RejectingVerifier(), Repairer()).run(
        "answer"
    )

    assert result.verification.status == VerificationStatus.PARTIAL
    assert result.draft.gaps == ["clutch context", "add clutch evidence"]

@pytest.mark.anyio
async def test_runtime_ledger_owns_turn_and_stage_lifecycle() -> None:
    from v2.runtime import LedgerKind, RunLedger

    ledger = RunLedger("run")
    instance = Runtime(
        intake=Intake(), planner=Planner(),
        executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}),
        synthesizer=Synthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
        ledger=ledger,
    )
    await instance.run("answer", run_id="run")

    kinds = [entry.kind for entry in ledger.entries]
    assert kinds[0] == LedgerKind.TURN_START
    assert kinds[-1] == LedgerKind.TURN_END
    starts = [entry.step_id for entry in ledger.entries
              if entry.kind == LedgerKind.STEP_START]
    ends = [entry.step_id for entry in ledger.entries
            if entry.kind == LedgerKind.STEP_END]
    assert starts == ["understand", "plan", "execute", "synthesize", "verify"]
    assert ends == starts
    assert ledger.entries[-1].data == {"reason": "complete", "verification": "pass"}


@pytest.mark.anyio
async def test_runtime_ledger_closes_failed_stage_and_turn() -> None:
    from v2.runtime import LedgerKind, RunLedger

    class BrokenIntake:
        async def understand(self, request):
            raise RuntimeError("bad input")

    ledger = RunLedger("run")
    instance = Runtime(
        intake=BrokenIntake(), planner=Planner(), executor=PlanExecutor({}),
        synthesizer=Synthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS), ledger=ledger)
    with pytest.raises(RuntimeError, match="bad input"):
        await instance.run("answer", run_id="run")

    assert [entry.kind for entry in ledger.entries] == [
        LedgerKind.TURN_START, LedgerKind.STEP_START,
        LedgerKind.STEP_END, LedgerKind.TURN_END]
    assert ledger.entries[-2].data["reason"] == "failed"
    assert ledger.entries[-1].data["reason"] == "failed"

@pytest.mark.anyio
async def test_runtime_passes_typed_context_to_intake() -> None:
    from v2.contracts import ConversationTurn

    class ContextIntake:
        async def understand(self, request, context=()):
            assert request == "Now assess his role"
            assert context[0].content == "Tell me about the Celtics"
            return TaskSpec(goal=request, mode=RunMode.QUICK, deliverable="text")

    instance = Runtime(
        intake=ContextIntake(), planner=Planner(),
        executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}),
        synthesizer=Synthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
    )
    await instance.run(
        "Now assess his role",
        context=(ConversationTurn(role="user", content="Tell me about the Celtics"),),
    )


@pytest.mark.anyio
async def test_semantic_verifier_never_sees_mechanically_rejected_draft() -> None:
    class MechanicalReject:
        async def verify(self, task, draft, evidence):
            return VerificationReport(
                status="repair",
                claim_results=[{"claim_index": 0, "supported": False,
                                "reasons": ["uncited numeral 43"]}],
            )

    class SemanticMustNotRun:
        async def verify(self, task, draft, evidence):
            raise AssertionError("semantic verifier saw ungrounded draft")

    result = await runtime(MechanicalReject(), SemanticMustNotRun()).run("answer")
    assert result.verification.status == VerificationStatus.PARTIAL
    assert result.verified_claims == []
    assert result.gaps[0].message == "uncited numeral 43"


@pytest.mark.anyio
async def test_runtime_honors_zero_repair_budget() -> None:
    mechanical = SequenceVerifier(VerificationStatus.REPAIR)
    semantic = SequenceVerifier(VerificationStatus.PASS)
    instance = runtime(mechanical, semantic, Repairer())
    instance._repair_attempts = 0
    result = await instance.run("answer")
    assert result.repaired is False
    assert result.verification.status == VerificationStatus.PARTIAL


@pytest.mark.anyio
async def test_runtime_honors_two_repair_budget() -> None:
    mechanical = SequenceVerifier(
        VerificationStatus.REPAIR, VerificationStatus.REPAIR,
        VerificationStatus.PASS)
    semantic = SequenceVerifier(VerificationStatus.PASS)
    instance = runtime(mechanical, semantic, Repairer())
    instance._repair_attempts = 2
    result = await instance.run("answer")
    assert result.repaired is True
    assert result.verification.status == VerificationStatus.PASS
