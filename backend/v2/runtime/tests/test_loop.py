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


@pytest.mark.parametrize("attempts,error", [
    (-1, "between 0 and 2"),
    (3, "between 0 and 2"),
    (True, "must be an integer"),
    (1.5, "must be an integer"),
])
def test_runtime_rejects_invalid_repair_budget(attempts, error) -> None:
    with pytest.raises((TypeError, ValueError), match=error):
        Runtime(
            intake=Intake(), planner=Planner(),
            executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}),
            synthesizer=Synthesizer(),
            mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
            semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
            repair_attempts=attempts,
        )


@pytest.mark.anyio
async def test_runtime_validates_direct_request_and_context_boundary() -> None:
    from v2.contracts import ConversationTurn

    instance = runtime(
        SequenceVerifier(VerificationStatus.PASS),
        SequenceVerifier(VerificationStatus.PASS),
    )
    for request in (" ", "x" * 2001):
        with pytest.raises(ValueError, match="request"):
            await instance.run(request)
    with pytest.raises(TypeError, match="request"):
        await instance.run(7)
    with pytest.raises(ValueError, match="8 turns"):
        await instance.run("answer", context=tuple(
            ConversationTurn(role="user", content=str(index))
            for index in range(9)
        ))
    invalid = ConversationTurn(role="user", content="valid").model_copy(
        update={"content": " "})
    with pytest.raises(ValueError, match="conversation content"):
        await instance.run("answer", context=(invalid,))


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
async def test_runtime_preserves_mechanical_support_when_semantic_omits_claim() -> None:
    class IncompleteSemanticVerifier:
        async def verify(self, task, draft, evidence):
            return VerificationReport(status=VerificationStatus.PARTIAL)

    result = await runtime(
        SequenceVerifier(VerificationStatus.PASS),
        IncompleteSemanticVerifier(),
    ).run("answer")
    assert [item.claim_index for item in result.verified_claims] == [0]
    assert result.verification.status == VerificationStatus.PARTIAL


def test_verification_merge_respects_report_field_limits() -> None:
    from v2.contracts import ClaimResult
    from v2.runtime.loop import _merge_verification

    mechanical = VerificationReport(
        status="partial",
        claim_results=[ClaimResult(
            claim_index=0, supported=False,
            reasons=[f"mechanical-{index}" for index in range(64)],
        )],
        missing_branches=[f"mechanical-gap-{index}" for index in range(128)],
    )
    semantic = VerificationReport(
        status="partial",
        claim_results=[ClaimResult(
            claim_index=0, supported=False,
            reasons=[f"semantic-{index}" for index in range(64)],
        )],
        missing_branches=[f"semantic-gap-{index}" for index in range(128)],
    )

    merged = _merge_verification(mechanical, semantic)

    assert len(merged.claim_results[0].reasons) == 64
    assert merged.claim_results[0].reasons == mechanical.claim_results[0].reasons
    assert len(merged.missing_branches) == 128
    assert merged.missing_branches == mechanical.missing_branches


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
async def test_runtime_revalidates_repairer_output() -> None:
    class InvalidRepairer:
        async def repair(self, task, draft, evidence, verification):
            return draft.model_copy(update={"sections": [" "]})

    instance = runtime(
        SequenceVerifier(VerificationStatus.REPAIR),
        SequenceVerifier(VerificationStatus.PASS),
        InvalidRepairer(),
    )
    with pytest.raises(ValueError, match="draft sections"):
        await instance.run("answer")


@pytest.mark.anyio
async def test_exhausted_repair_bounds_combined_draft_gaps() -> None:
    class MaxFindingVerifier:
        async def verify(self, task, draft, evidence):
            return VerificationReport(
                status=VerificationStatus.REPAIR,
                claim_results=[{
                    "claim_index": index, "supported": True,
                } for index, _claim in enumerate(draft.claims)],
                missing_branches=[f"missing-{index}" for index in range(128)],
                repair_instructions=[f"repair-{index}" for index in range(128)],
            )

    result = await runtime(
        MaxFindingVerifier(), MaxFindingVerifier(), Repairer(),
    ).run("answer")

    assert result.verification.status == VerificationStatus.PARTIAL
    assert len(result.draft.gaps) == 128
    assert result.draft.gaps == [f"missing-{index}" for index in range(128)]


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
    assert result.draft.gaps == ["clutch context"]

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
    assert ledger.entries[-1].data["reason"] == "complete"
    assert ledger.entries[-1].data["verification"] == "pass"
    assert ledger.entries[-1].data["duration_ms"] >= 0
    assert all(entry.data["duration_ms"] >= 0 for entry in ledger.entries
               if entry.kind == LedgerKind.STEP_END)


@pytest.mark.anyio
async def test_progress_observer_failure_cannot_break_runtime_or_ledger() -> None:
    from v2.runtime import LedgerKind, RunLedger

    statuses = []

    def broken_progress(step_id, status):
        statuses.append((step_id, status))
        raise RuntimeError("observer unavailable")

    ledger = RunLedger("run")
    instance = Runtime(
        intake=Intake(), planner=Planner(),
        executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}),
        synthesizer=Synthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
        ledger=ledger, progress=broken_progress,
    )
    result = await instance.run("answer", run_id="run")

    assert result.verification.status == VerificationStatus.PASS
    assert statuses[0] == ("understand", "running")
    assert statuses[-1] == ("verify", "complete")
    assert ledger.entries[-1].kind == LedgerKind.TURN_END
    assert ledger.entries[-1].data["reason"] == "complete"


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
async def test_empty_synthesis_cannot_publish_a_blank_clean_pass() -> None:
    class EmptySynthesizer:
        async def synthesize(self, task, evidence):
            return DraftReport(sections=[], claims=[])

    instance = Runtime(
        intake=Intake(), planner=Planner(),
        executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}),
        synthesizer=EmptySynthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
    )
    result = await instance.run("answer")

    assert result.verification.status == VerificationStatus.PARTIAL
    assert result.verified_claims == []
    assert [gap.message for gap in result.gaps] == [
        "synthesis produced no publishable claims",
    ]


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
    assert result.verified_claims == []
    assert any(gap.kind == "execution_failure" for gap in result.gaps)
    unsupported = [gap for gap in result.gaps if gap.kind == "unsupported_claim"]
    assert unsupported
    assert unsupported[0].evidence_ids == []


@pytest.mark.anyio
async def test_recovered_retry_error_does_not_downgrade_verified_result() -> None:
    class RetryPlanner:
        async def plan(self, task):
            return Plan(nodes=[PlanNode(
                id="facts", description="facts", capability_hints=["fake"],
                max_attempts=2,
            )])

    instance = Runtime(
        intake=Intake(), planner=RetryPlanner(),
        executor=PlanExecutor({
            "fake": FakeCapability("fake", {"value": 42}, failures_before_success=1),
        }),
        synthesizer=Synthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
    )
    result = await instance.run("answer")
    assert result.execution.errors == {
        "facts": ["RuntimeError: injected capability failure"],
    }
    assert result.verification.status == VerificationStatus.PASS
    assert result.gaps == []


@pytest.mark.anyio
async def test_model_authored_gap_downgrades_clean_verification_to_partial() -> None:
    class GapSynthesizer:
        async def synthesize(self, task, evidence):
            return DraftReport(
                sections=["No sourced answer"], claims=[],
                gaps=["The requested split was unavailable"],
            )

    instance = Runtime(
        intake=Intake(), planner=Planner(),
        executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}),
        synthesizer=GapSynthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
    )
    result = await instance.run("answer")
    assert result.verification.status == VerificationStatus.PARTIAL
    assert [gap.message for gap in result.gaps] == [
        "The requested split was unavailable",
    ]


@pytest.mark.anyio
async def test_unexplained_partial_verification_returns_typed_gap() -> None:
    class UnexplainedPartialVerifier:
        async def verify(self, task, draft, evidence):
            return VerificationReport(
                status=VerificationStatus.PARTIAL,
                claim_results=[{
                    "claim_index": index, "supported": True,
                } for index, _claim in enumerate(draft.claims)],
            )

    result = await runtime(
        SequenceVerifier(VerificationStatus.PASS),
        UnexplainedPartialVerifier(),
    ).run("answer")

    assert result.verification.status == VerificationStatus.PARTIAL
    assert [gap.message for gap in result.gaps] == [
        "verification did not establish complete support",
    ]
    assert result.verified_claims[0].claim.text == "42"


@pytest.mark.anyio
async def test_partial_repair_instruction_surfaces_as_typed_gap() -> None:
    class PartialSemanticVerifier:
        async def verify(self, task, draft, evidence):
            return VerificationReport(
                status=VerificationStatus.PARTIAL,
                claim_results=[{
                    "claim_index": index, "supported": True,
                } for index, _claim in enumerate(draft.claims)],
                repair_instructions=["Add a second source for role context"],
            )

    result = await runtime(
        SequenceVerifier(VerificationStatus.PASS),
        PartialSemanticVerifier(),
    ).run("answer")

    assert result.verification.status == VerificationStatus.PARTIAL
    assert [gap.message for gap in result.gaps] == [
        "verification did not establish complete support",
    ]


@pytest.mark.anyio
async def test_runtime_bounds_combined_typed_publication_gaps() -> None:
    class ManyGapSynthesizer:
        async def synthesize(self, task, evidence):
            return DraftReport(
                sections=["No answer"], claims=[],
                gaps=[f"draft-{index}" for index in range(128)],
            )

    class ManyFindingVerifier:
        async def verify(self, task, draft, evidence):
            return VerificationReport(
                status=VerificationStatus.PARTIAL,
                missing_branches=[f"missing-{index}" for index in range(128)],
                contradictions=[f"conflict-{index}" for index in range(128)],
            )

    instance = Runtime(
        intake=Intake(), planner=Planner(),
        executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}),
        synthesizer=ManyGapSynthesizer(),
        mechanical_verifier=ManyFindingVerifier(),
        semantic_verifier=ManyFindingVerifier(),
    )
    result = await instance.run("answer")

    assert len(result.gaps) == 256
    assert [gap.message for gap in result.gaps[:128]] == [
        f"draft-{index}" for index in range(128)
    ]
    assert [gap.message for gap in result.gaps[128:]] == [
        f"missing-{index}" for index in range(128)
    ]


@pytest.mark.anyio
async def test_skipped_execution_node_prevents_clean_pass() -> None:
    class SkippedExecutor:
        async def execute(self, task, plan, run_id=None):
            from v2.runtime.models import ExecutionResult
            from v2.contracts import PlanStatus
            skipped = plan.nodes[0].model_copy(update={"status": PlanStatus.SKIPPED})
            return ExecutionResult(plan=Plan(nodes=[skipped]))

    class EmptySynthesizer:
        async def synthesize(self, task, evidence):
            return DraftReport(sections=["No answer"], claims=[])

    instance = Runtime(
        intake=Intake(), planner=Planner(), executor=SkippedExecutor(),
        synthesizer=EmptySynthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
    )
    result = await instance.run("answer")

    assert result.verification.status == VerificationStatus.PARTIAL
    assert len(result.gaps) == 1
    assert result.gaps[0].kind == "execution_failure"
    assert result.gaps[0].message == "execution skipped node facts"
    assert result.gaps[0].blocks == ["node:facts"]


@pytest.mark.anyio
async def test_runtime_revalidates_component_results() -> None:
    class InvalidIntake(Intake):
        async def understand(self, request):
            valid = await super().understand(request)
            return valid.model_copy(update={"goal": " "})

    instance = runtime(SequenceVerifier(VerificationStatus.PASS),
                       SequenceVerifier(VerificationStatus.PASS))
    instance._intake = InvalidIntake()
    with pytest.raises(ValueError, match="goal and deliverable"):
        await instance.run("question")

@pytest.mark.anyio
async def test_progress_never_projects_stage_before_start_is_recorded() -> None:
    from v2.runtime import RunLedger

    class StartRejectingLedger:
        def __init__(self):
            self.run_id = "run"
            self.inner = RunLedger("run")

        def append(self, kind, **kwargs):
            if kind.value == "step/start":
                raise OSError("ledger unavailable")
            return self.inner.append(kind, **kwargs)

    statuses = []
    instance = Runtime(
        intake=Intake(), planner=Planner(), executor=PlanExecutor({}),
        synthesizer=Synthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
        ledger=StartRejectingLedger(),
        progress=lambda step_id, status: statuses.append((step_id, status)),
    )

    with pytest.raises(OSError, match="ledger unavailable"):
        await instance.run("answer", run_id="run")

    assert statuses == []


@pytest.mark.anyio
async def test_progress_never_projects_completion_before_end_is_recorded() -> None:
    from v2.runtime import RunLedger

    class EndRejectingLedger:
        def __init__(self):
            self.run_id = "run"
            self.inner = RunLedger("run")

        def append(self, kind, **kwargs):
            if kind.value == "step/end" and kwargs.get("data", {}).get("reason") == "complete":
                raise OSError("ledger unavailable")
            return self.inner.append(kind, **kwargs)

    statuses = []
    instance = Runtime(
        intake=Intake(), planner=Planner(), executor=PlanExecutor({}),
        synthesizer=Synthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
        ledger=EndRejectingLedger(),
        progress=lambda step_id, status: statuses.append((step_id, status)),
    )

    with pytest.raises((OSError, ValueError)):
        await instance.run("answer", run_id="run")

    assert ("understand", "running") in statuses
    assert ("understand", "complete") not in statuses

@pytest.mark.anyio
async def test_incomplete_semantic_results_preserve_mechanically_supported_claims() -> None:
    class TwoClaimSynthesizer:
        async def synthesize(self, task, evidence):
            return DraftReport(sections=["Answer"], claims=[
                Claim(text="First fact", kind="observed", evidence_ids=["evidence:facts"]),
                Claim(text="Second fact", kind="observed", evidence_ids=["evidence:facts"]),
            ])

    class Mechanical:
        async def verify(self, task, draft, evidence):
            return VerificationReport(status="pass", claim_results=[
                {"claim_index": 0, "supported": True},
                {"claim_index": 1, "supported": True},
            ])

    class IncompleteSemantic:
        async def verify(self, task, draft, evidence):
            return VerificationReport(
                status="partial",
                claim_results=[{"claim_index": 0, "supported": True}],
                missing_branches=["another branch was unavailable"],
            )

    instance = Runtime(
        intake=Intake(), planner=Planner(),
        executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}),
        synthesizer=TwoClaimSynthesizer(), mechanical_verifier=Mechanical(),
        semantic_verifier=IncompleteSemantic(),
    )
    result = await instance.run("answer")
    assert [item.claim_index for item in result.verified_claims] == [0, 1]
    assert [item.claim.text for item in result.verified_claims] == ["First fact", "Second fact"]
    assert result.verification.status == VerificationStatus.PARTIAL


def test_unresolved_repair_instructions_do_not_become_public_gaps():
    from v2.runtime.loop import _verification_gaps
    report = VerificationReport(status="repair", repair_instructions=[
        "Replace Houston with San Antonio in claim 1.",
    ])
    assert _verification_gaps(DraftReport(sections=[], claims=[]), report) == []

@pytest.mark.anyio
async def test_runtime_flags_repair_that_strips_evidence_claim():
    from v2.contracts import Claim, DraftReport

    class EvidenceDraft:
        async def synthesize(self, task, evidence):
            return DraftReport(sections=["Answer"], claims=[Claim(
                text="Atlanta led with 2462 assists.", kind="observed",
                evidence_ids=[evidence[0].evidence_id],
            )])

    class StripRepair:
        async def repair(self, task, draft, evidence, verification):
            return DraftReport(sections=["Repaired"], claims=[],
                               gaps=["leader claim was rejected"])

    instance = runtime(
        SequenceVerifier(VerificationStatus.REPAIR, VerificationStatus.PASS),
        SequenceVerifier(VerificationStatus.PASS, VerificationStatus.PASS),
        StripRepair(),
    )
    instance._synthesizer = EvidenceDraft()
    result = await instance.run("team assist leader")

    assert result.structural_flags == ["repair_stripped_evidence_claim"]


@pytest.mark.anyio
async def test_runtime_does_not_flag_repair_that_preserves_evidence_claim():
    result = await runtime(
        SequenceVerifier(VerificationStatus.REPAIR, VerificationStatus.PASS),
        SequenceVerifier(VerificationStatus.PASS, VerificationStatus.PASS),
        Repairer(),
    ).run("answer")
    assert result.structural_flags == []


@pytest.mark.anyio
async def test_pre_tool_timeout_closes_stage_and_turn_without_execution() -> None:
    import asyncio
    from v2.runtime import LedgerKind, PreToolTimeoutError, RunLedger

    class SlowIntake:
        async def understand(self, request):
            await asyncio.sleep(0.05)
            return TaskSpec(goal=request, mode=RunMode.QUICK, deliverable="text")

    ledger = RunLedger("run")
    instance = Runtime(
        intake=SlowIntake(), planner=Planner(), executor=PlanExecutor({}),
        synthesizer=Synthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
        ledger=ledger, pre_tool_timeout_s=0.001)
    with pytest.raises(PreToolTimeoutError, match="intake and planning exceeded"):
        await instance.run("answer", run_id="run")

    terminal = [entry for entry in ledger.entries
                if entry.kind in {LedgerKind.STEP_END, LedgerKind.TURN_END}]
    assert [entry.data["reason"] for entry in terminal] == ["timeout", "timeout"]
    assert all(entry.data["duration_ms"] >= 0 for entry in terminal)
    assert not any(entry.kind == LedgerKind.TOOL_CALL for entry in ledger.entries)


@pytest.mark.anyio
async def test_verified_claim_sources_preserve_per_fact_vintage() -> None:
    from datetime import UTC, date, datetime
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.loop import _verified_claims

    claim = Claim(text="The salary is $57.1M.", kind="observed",
                  evidence_ids=["salary"] )
    draft = DraftReport(sections=["Answer"], claims=[claim])
    verification = VerificationReport(
        status="pass", claim_results=[{
            "claim_index": 0, "supported": True, "reasons": []}])
    envelope = EvidenceEnvelope(
        evidence_id="salary", capability="trade_value", source="fixture",
        observed_at=datetime(2026, 9, 17, tzinfo=UTC),
        as_of=date(2026, 7, 1), vintages={"salary_season": "2026-27"},
        task_season_scoped=False, rows={"salary": 57_100_000})

    source = _verified_claims(
        draft, verification, {"salary": envelope})[0].sources[0]
    assert source.vintages == {"salary_season": "2026-27"}
    assert source.as_of == date(2026, 7, 1)
    assert source.observed_at == datetime(2026, 9, 17, tzinfo=UTC)

@pytest.mark.anyio
async def test_redundant_failed_capability_does_not_create_false_partial():
    from v2.runtime.models import ExecutionResult
    from v2.contracts import PlanStatus

    class RedundantIntake:
        async def understand(self, request):
            return TaskSpec(
                goal=request, mode="quick", deliverable="answer",
                requirements=[{
                    "id": "efficiency", "description": "player efficiency",
                    "capability_options": [
                        "player_report", "shooting_efficiency"],
                }],
            )

    class RedundantPlanner:
        async def plan(self, task):
            return Plan(nodes=[
                PlanNode(
                    id="report", description="full report",
                    capability_hints=["player_report"],
                    arguments={"player_id": 201939, "season": "2025-26"},
                    covers_requirement_ids=["efficiency"],
                ),
                PlanNode(
                    id="efficiency", description="redundant efficiency",
                    capability_hints=["shooting_efficiency"],
                    arguments={"player_id": 201939, "season": "2025-26"},
                    covers_requirement_ids=["efficiency"],
                ),
            ])

    class RedundantExecutor:
        async def execute(self, task, plan, run_id=None):
            evidence = await FakeCapability(
                "player_report", {"TS_PCT": 0.65},
            ).execute(plan.nodes[0], task, ())
            return ExecutionResult(
                plan=Plan(nodes=[
                    plan.nodes[0].model_copy(update={"status": PlanStatus.COMPLETE}),
                    plan.nodes[1].model_copy(update={"status": PlanStatus.FAILED}),
                ]),
                evidence=[evidence], attempts={"report": 1, "efficiency": 1},
                errors={"efficiency": ["TimeoutError: source timed out"]},
            )

    class ReportSynthesizer:
        async def synthesize(self, task, evidence):
            return DraftReport(sections=["Answer"], claims=[Claim(
                text="His true shooting percentage was 65%.",
                kind="observed", evidence_ids=["evidence:report"],
            )])

    result = await Runtime(
        intake=RedundantIntake(), planner=RedundantPlanner(),
        executor=RedundantExecutor(), synthesizer=ReportSynthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
    ).run("Assess his scoring efficiency")

    assert result.verification.status == VerificationStatus.PASS
    assert result.gaps == []
    assert result.structural_flags == ["false_partial_downgrade"]

@pytest.mark.anyio
async def test_runtime_does_not_flag_corrected_rejected_claim_as_stripped_supported_branch():
    from v2.contracts import Claim, DraftReport

    class OriginalDraft:
        async def synthesize(self, task, evidence):
            return DraftReport(sections=["Answer"], claims=[
                Claim(text="Atlanta had the best record.", kind="observed",
                      evidence_ids=[evidence[0].evidence_id]),
                Claim(text="Atlanta finished 60-22.", kind="observed",
                      evidence_ids=[evidence[0].evidence_id]),
            ])

    class CorrectRejected:
        async def repair(self, task, draft, evidence, verification):
            return DraftReport(sections=["Answer"], claims=[
                draft.claims[1],
                Claim(text="Atlanta had the best record at 60-22.", kind="observed",
                      evidence_ids=draft.claims[0].evidence_ids),
            ])

    class RejectFirstThenPass:
        def __init__(self): self.calls = 0
        async def verify(self, task, draft, evidence):
            self.calls += 1
            return VerificationReport(
                status=(VerificationStatus.REPAIR if self.calls == 1
                        else VerificationStatus.PASS),
                claim_results=[
                    {"claim_index": index,
                     "supported": self.calls > 1 or index == 1,
                     "reasons": (["incomplete record"]
                                 if self.calls == 1 and index == 0 else [])}
                    for index, _claim in enumerate(draft.claims)
                ],
            )

    instance = runtime(
        RejectFirstThenPass(),
        SequenceVerifier(VerificationStatus.PASS, VerificationStatus.PASS),
        CorrectRejected(),
    )
    instance._synthesizer = OriginalDraft()
    result = await instance.run("best record")
    assert result.structural_flags == []
@pytest.mark.anyio
async def test_uncovered_requirement_preserves_supported_partial_branch():
    class PartialIntake:
        async def understand(self, request):
            return TaskSpec(
                goal=request, mode="deep_dive", deliverable="answer",
                requirements=[
                    {"id": "record", "description": "identify best record",
                     "capability_options": ["fake"]},
                    {"id": "unknown_player", "description":
                     "evaluate the contributor whose identity is not grounded",
                     "capability_options": ["player_report"]},
                ],
            )

    class PartialPlanner:
        async def plan(self, task):
            return Plan(nodes=[PlanNode(
                id="record", description="record", capability_hints=["fake"],
                covers_requirement_ids=["record"],
            )])

    class PartialSynthesizer:
        async def synthesize(self, task, evidence):
            return DraftReport(sections=["Answer"], claims=[Claim(
                text="42", kind=ClaimKind.OBSERVED,
                evidence_ids=[evidence[0].evidence_id],
            )])

    result = await Runtime(
        intake=PartialIntake(), planner=PartialPlanner(),
        executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}),
        synthesizer=PartialSynthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
    ).run("Who led, and evaluate the unknown contributor")

    assert len(result.verified_claims) == 1
    assert result.verification.status == VerificationStatus.PARTIAL
    assert [(gap.message, gap.blocks) for gap in result.gaps] == [
        ("Uncovered requirement: evaluate the contributor whose identity is not grounded",
         ["requirement:unknown_player"]),
    ]
