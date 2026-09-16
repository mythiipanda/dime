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
