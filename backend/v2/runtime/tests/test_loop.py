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
        status = self.statuses.pop(0)
        return VerificationReport(
            status=status,
            claim_results=[
                {"claim_index": index, "supported": True}
                for index, _claim in enumerate(draft.claims)
            ],
            repair_instructions=(
                ["repair requested"]
                if status == VerificationStatus.REPAIR else []
            ),
        )


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
async def test_runtime_rejects_incomplete_swappable_mechanical_verifier() -> None:
    class IncompleteMechanicalVerifier:
        async def verify(self, task, draft, evidence):
            return VerificationReport(status=VerificationStatus.PASS)

    with pytest.raises(ValueError, match="mechanical verifier must adjudicate"):
        await runtime(
            IncompleteMechanicalVerifier(),
            SequenceVerifier(VerificationStatus.PASS),
        ).run("answer")


@pytest.mark.anyio
async def test_runtime_rejects_incomplete_swappable_semantic_verifier() -> None:
    class IncompleteSemanticVerifier:
        async def verify(self, task, draft, evidence):
            return VerificationReport(status=VerificationStatus.PASS)

    with pytest.raises(ValueError, match="adjudicate every claim exactly once"):
        await runtime(
            SequenceVerifier(VerificationStatus.PASS),
            IncompleteSemanticVerifier(),
        ).run("answer")


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
                claim_results=[{
                    "claim_index": index, "supported": True,
                } for index, _claim in enumerate(draft.claims)],
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


@pytest.mark.anyio
async def test_unresolved_intake_questions_stop_before_planning() -> None:
    class AmbiguousIntake:
        async def understand(self, request):
            return TaskSpec(
                goal=request, mode="quick", deliverable="answer",
                open_questions=["Which Brown do you mean?"],
            )

    class MustNotPlan:
        async def plan(self, task):
            raise AssertionError("planner ran on ambiguous task")

    instance = Runtime(
        intake=AmbiguousIntake(), planner=MustNotPlan(),
        executor=PlanExecutor({}), synthesizer=Synthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
    )
    with pytest.raises(ValueError, match="Which Brown"):
        await instance.run("assess Brown")


@pytest.mark.anyio
async def test_empty_evidence_cannot_finish_as_a_clean_pass() -> None:
    class EmptySynthesizer:
        async def synthesize(self, task, evidence):
            return DraftReport(sections=["No sourced answer"], claims=[])

    instance = Runtime(
        intake=Intake(), planner=Planner(),
        executor=PlanExecutor({"fake": FakeCapability("fake", [])}),
        synthesizer=EmptySynthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
    )
    result = await instance.run("answer")
    assert result.verification.status == VerificationStatus.PARTIAL
    assert len(result.gaps) == 1
    assert result.gaps[0].kind == "missing_evidence"
    assert result.gaps[0].evidence_ids == ["evidence:facts"]


@pytest.mark.anyio
async def test_execution_failure_prevents_clean_pass_status() -> None:
    class FailedExecutor:
        async def execute(self, task, plan, run_id=None):
            from v2.runtime.models import ExecutionResult
            from v2.contracts import PlanStatus
            failed = plan.nodes[0].model_copy(update={"status": PlanStatus.FAILED})
            return ExecutionResult(
                plan=Plan(nodes=[failed]), attempts={failed.id: 1},
                errors={failed.id: ["RuntimeError: source down"]})

    instance = Runtime(
        intake=Intake(), planner=Planner(), executor=FailedExecutor(),
        synthesizer=Synthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS))
    result = await instance.run("answer")
    assert result.verification.status == VerificationStatus.PARTIAL
    assert any(gap.kind == "execution_failure" for gap in result.gaps)
