from __future__ import annotations
from datetime import UTC, datetime
from v2.contracts import EvidenceEnvelope, Plan, PlanNode, PlanStatus
from v2.runtime.loop import _merge_recovery as merge
from v2.runtime.models import ExecutionResult


def test_recovery_child_lineage_follows_renamed_parent():
    execution = ExecutionResult(
        plan=Plan(nodes=[
            PlanNode(
                id="p1",
                description="parent attempt",
                capability_hints=["cap_a"],
                covers_requirement_ids=["scoring"],
                status=PlanStatus.FAILED,
            ),
            PlanNode(
                id="c1",
                description="child attempt",
                capability_hints=["cap_c"],
                covers_requirement_ids=["efficiency"],
                status=PlanStatus.FAILED,
            ),
        ]),
        attempts={"p1": 1, "c1": 1},
        errors={"p1": ["RuntimeError: p1 failed"], "c1": ["RuntimeError: c1 failed"]},
    )
    now = datetime.now(UTC)
    recovery = ExecutionResult(
        plan=Plan(nodes=[
            PlanNode(
                id="p1",
                description="parent recovery",
                capability_hints=["cap_a"],
                covers_requirement_ids=["scoring"],
                status=PlanStatus.COMPLETE,
            ),
            PlanNode(
                id="c1",
                description="child recovery",
                capability_hints=["cap_c"],
                covers_requirement_ids=["efficiency"],
                depends_on=["p1"],
                status=PlanStatus.COMPLETE,
            ),
        ]),
        evidence_by_node={
            "p1": EvidenceEnvelope(
                evidence_id="evidence:p1",
                capability="cap_a",
                source="fake",
                observed_at=now,
                rows={"value": 1},
                lineage=[],
            ),
            "c1": EvidenceEnvelope(
                evidence_id="evidence:c1",
                capability="cap_c",
                source="fake",
                observed_at=now,
                rows={"value": 1},
                lineage=["evidence:p1"],
            ),
        },
        attempts={"p1": 1, "c1": 1},
    )
    merged = merge(execution, recovery)
    assert isinstance(merged, ExecutionResult)
    assert merged.evidence_by_node["c1-replan2"].lineage == ["evidence:p1-replan2"]
