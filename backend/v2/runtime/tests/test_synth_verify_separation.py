from __future__ import annotations

import pytest
from v2.contracts import Claim, ClaimKind, DraftReport, Plan, PlanNode, RunMode, TaskSpec, VerificationReport, VerificationStatus
from v2.runtime import FakeCapability, PlanExecutor, Runtime
from v2.runtime.interfaces import freeze_draft, freeze_evidence, freeze_evidence_map, reject_self_verified_draft, validate_repair_evidence_closed, RepairAddsEvidenceError

@pytest.fixture
def anyio_backend():
    return "asyncio"

def _task() -> TaskSpec:
    return TaskSpec(goal="answer", mode=RunMode.QUICK, deliverable="text")

def _draft() -> DraftReport:
    return DraftReport(sections=["Answer"], claims=[Claim(text="42", kind=ClaimKind.OBSERVED, evidence_ids=["evidence:facts"])])

def _evidence_map():
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope
    envelope = EvidenceEnvelope(evidence_id="evidence:facts", capability="fake", source="fake", observed_at=datetime.now(UTC), rows={"value": 42})
    return {"evidence:facts": envelope}

def test_verifier_draft_mutation_fails() -> None:
    frozen = freeze_draft(_draft())
    with pytest.raises(Exception):
        frozen.sections.append("smuggled")
    with pytest.raises(Exception):
        frozen.claims[0].text = "smuggled"
    with pytest.raises(Exception):
        frozen.claims.append(frozen.claims[0])
    with pytest.raises(Exception):
        frozen.gaps.append("smuggled")
    assert frozen.sections == ("Answer",)
    assert frozen.claims[0].text == "42"

def test_verifier_evidence_mutation_fails() -> None:
    frozen = freeze_evidence_map(_evidence_map())
    with pytest.raises(Exception):
        frozen["evidence:new"] = list(frozen.values())[0]
    envelope = frozen["evidence:facts"]
    with pytest.raises(Exception):
        envelope.capability = "smuggled"
    with pytest.raises(Exception):
        envelope.units["smuggled"] = "x"
    with pytest.raises(Exception):
        envelope.warnings.append("smuggled")
    with pytest.raises(Exception):
        envelope.model_copy(update={"capability": "smuggled"})
    assert envelope.capability == "fake"

def test_verifier_evidence_rows_mutation_fails() -> None:
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope
    envelope = EvidenceEnvelope(evidence_id="e", capability="fake", source="fake", observed_at=datetime.now(UTC), rows=[{"value": 1}])
    frozen = freeze_evidence(envelope)
    with pytest.raises(Exception):
        frozen.rows.append({"value": 2})
    with pytest.raises(Exception):
        frozen.rows[0]["value"] = 2

def test_repair_cannot_add_evidence_id() -> None:
    admitted = _evidence_map()
    repaired = DraftReport(sections=["Answer"], claims=[Claim(text="42 plus extra", kind=ClaimKind.OBSERVED, evidence_ids=["evidence:smuggled"])])
    with pytest.raises(RepairAddsEvidenceError, match="evidence:smuggled"):
        validate_repair_evidence_closed(admitted, repaired)

def test_repair_may_drop_claims() -> None:
    admitted = _evidence_map()
    repaired = DraftReport(sections=["Answer"], claims=[])
    validate_repair_evidence_closed(admitted, repaired)

def test_self_verified_draft_rejected() -> None:
    with pytest.raises(ValueError, match="cannot mark its own claims verified"):
        reject_self_verified_draft({"sections": ["A"], "claims": [], "status": "pass"})
    with pytest.raises(ValueError, match="cannot mark its own claims verified"):
        reject_self_verified_draft({"sections": ["A"], "claims": [{"text": "x", "supported": True}]})
    with pytest.raises(ValueError, match="cannot mark its own claims verified"):
        reject_self_verified_draft(VerificationReport(status=VerificationStatus.PASS))

class _Intake:
    async def understand(self, request: str) -> TaskSpec:
        return TaskSpec(goal=request, mode=RunMode.QUICK, deliverable="text")

class _Planner:
    async def plan(self, task: TaskSpec) -> Plan:
        return Plan(nodes=[PlanNode(id="facts", description="facts", capability_hints=["fake"])])

class _Synth:
    async def synthesize(self, task, evidence) -> DraftReport:
        return DraftReport(sections=["Answer"], claims=[Claim(text="42", kind=ClaimKind.OBSERVED, evidence_ids=["evidence:facts"])])

class _Pass:
    async def verify(self, task, draft, evidence) -> VerificationReport:
        return VerificationReport(status=VerificationStatus.PASS, claim_results=[{"claim_index": index, "supported": True} for index, _claim in enumerate(draft.claims)])

def _runtime(mech, sem, repairer=None) -> Runtime:
    return Runtime(intake=_Intake(), planner=_Planner(), executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}), synthesizer=_Synth(), mechanical_verifier=mech, semantic_verifier=sem, repairer=repairer)

@pytest.mark.anyio
async def test_loop_rejects_mutating_verifier() -> None:
    class Mutating:
        async def verify(self, task, draft, evidence):
            draft.sections.append("smuggled")
            return VerificationReport(status=VerificationStatus.PASS, claim_results=[{"claim_index": index, "supported": True} for index, _claim in enumerate(draft.claims)])
    with pytest.raises(Exception, match="read-only|mutat|no attribute"):
        await _runtime(Mutating(), _Pass()).run("answer")

@pytest.mark.anyio
async def test_loop_rejects_repair_adding_evidence() -> None:
    class AddingRepair:
        async def repair(self, task, draft, evidence, verification) -> DraftReport:
            return DraftReport(sections=["R"], claims=[Claim(text="smuggled 43", kind=ClaimKind.OBSERVED, evidence_ids=["evidence:smuggled"])])

    class RejectOnce:
        def __init__(self) -> None:
            self.calls = 0
        async def verify(self, task, draft, evidence):
            self.calls += 1
            if self.calls == 1:
                return VerificationReport(status=VerificationStatus.REPAIR, claim_results=[{"claim_index": index, "supported": False, "reasons": ["uncited numeral 42"]} for index, _claim in enumerate(draft.claims)], repair_instructions=["fix"])
            return VerificationReport(status=VerificationStatus.PASS, claim_results=[{"claim_index": index, "supported": True} for index, _claim in enumerate(draft.claims)])
    with pytest.raises(RepairAddsEvidenceError, match="evidence:smuggled"):
        await _runtime(RejectOnce(), _Pass(), AddingRepair()).run("answer")

@pytest.mark.anyio
async def test_loop_rejects_self_verified_synthesizer() -> None:
    class SelfVerified:
        async def synthesize(self, task, evidence):
            return {"sections": ["Answer"], "claims": [], "status": "pass", "claim_results": []}
    instance = Runtime(intake=_Intake(), planner=_Planner(), executor=PlanExecutor({"fake": FakeCapability("fake", {"value": 42})}), synthesizer=SelfVerified(), mechanical_verifier=_Pass(), semantic_verifier=_Pass())
    with pytest.raises(ValueError, match="cannot mark its own claims verified"):
        await instance.run("answer")
