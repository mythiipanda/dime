from datetime import UTC, datetime

import pytest

from v2.contracts import EvidenceEnvelope, PlanNode, RunMode, TaskSpec
from v2.runtime import LedgerKind, RecordedCapability, RunLedger


class Capability:
    name = "standings"

    async def execute(self, node, task, evidence):
        return EvidenceEnvelope(evidence_id="ev", capability=self.name,
            source="fixture", observed_at=datetime.now(UTC), rows={"wins": 61})


@pytest.mark.anyio
async def test_recorded_capability_emits_canonical_call_and_result():
    ledger = RunLedger("run")
    capability = RecordedCapability(Capability(), ledger, turn_id="turn")
    await capability.execute(
        PlanNode(id="record", description="record", capability_hints=["standings"]),
        TaskSpec(goal="record", mode=RunMode.QUICK, deliverable="text"), [])

    assert [entry.kind for entry in ledger.entries] == [
        LedgerKind.TOOL_CALL, LedgerKind.TOOL_RESULT]
    assert ledger.entries[0].call_id == ledger.entries[1].call_id
    assert ledger.entries[1].data["evidence"]["evidence_id"] == "ev"


@pytest.mark.anyio
async def test_recorded_capability_rejects_untyped_result_and_records_failure():
    class Untyped:
        name = "standings"
        async def execute(self, node, task, evidence):
            return {"wins": 61}

    ledger = RunLedger("run")
    capability = RecordedCapability(Untyped(), ledger, turn_id="turn")
    with pytest.raises(TypeError, match="EvidenceEnvelope"):
        await capability.execute(
            PlanNode(id="record", description="record", capability_hints=["standings"]),
            TaskSpec(goal="record", mode=RunMode.QUICK, deliverable="text"), [],
        )
    assert ledger.entries[-1].data == {
        "status": "failed", "error": "TypeError: capability must return EvidenceEnvelope"
    }


def test_recorded_capability_requires_identity() -> None:
    class Blank(Capability):
        name = " "

    with pytest.raises(ValueError, match="name must be non-empty"):
        RecordedCapability(Blank(), RunLedger("run"), turn_id="turn")
    with pytest.raises(ValueError, match="turn id must be non-empty"):
        RecordedCapability(Capability(), RunLedger("run"), turn_id=" ")
