from datetime import UTC, datetime

import pytest

from v2.contracts import (
    Claim,
    ClaimSource,
    DraftReport,
    EvidenceEnvelope,
    EvidenceOutputBinding,
    Plan,
    PlanNode,
    TaskSpec,
    VerifiedClaim,
)
from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings

_NODE_ID = "query_player_ts"
_EVIDENCE_ID = "sql_exec:9f21c0d4"
_PERCENT = "percent_0_100"
_VALUE = 0.614

def _envelope(units, capability="sql_exec"):
    return EvidenceEnvelope(
        evidence_id=_EVIDENCE_ID,
        capability=capability,
        source=f"v1:{capability}:warehouse",
        observed_at=datetime.now(UTC),
        season="2024-25",
        rows=[{"PLAYER_NAME": "Player One", "TS_PCT": _VALUE,
               "n": _VALUE, "NET_RATING": _VALUE}],
        units=units,
    )

def _task(outputs):
    return TaskSpec(
        goal="which ten players lead on true shooting in 2024-25",
        mode="quick",
        deliverable="ten names with their true shooting percentage",
        requested_outputs=list(outputs),
    )

def _binding(unit, *, value=_VALUE, output_id="TS_PCT", leaf="TS_PCT",
             domain="sql_exec"):
    return EvidenceOutputBinding(
        requirement_kind="task",
        requirement_id=None,
        output_id=output_id,
        node_id=_NODE_ID,
        evidence_id=_EVIDENCE_ID,
        selector=f"rows[0].{leaf}",
        value={"kind": "float", "value": value},
        unit=unit,
        domain=domain,
    )

def _admit(binding, envelope, outputs, capability="sql_exec"):
    execution = ExecutionResult(
        plan=Plan(nodes=[PlanNode(
            id=_NODE_ID,
            description="agent-written true shooting ranking",
            capability_hints=[capability],
            status="complete")]),
        evidence_by_node={_NODE_ID: envelope},
        attempts={_NODE_ID: 1},
    )
    claim = Claim(
        text="Player One posted a 61.4 percent true shooting percentage.",
        kind="observed",
        evidence_ids=[envelope.evidence_id],
        output_bindings=[binding],
    )
    draft = DraftReport(sections=["answer"], claims=[claim])
    verified = VerifiedClaim(
        claim_index=0,
        claim=claim,
        evidence_ids=[envelope.evidence_id],
        sources=[ClaimSource(
            evidence_id=envelope.evidence_id,
            source=envelope.source,
            capability=envelope.capability,
            observed_at=envelope.observed_at,
        )],
        output_bindings=[binding],
    )
    return admit_verified_claim_bindings(
        _task(outputs), execution, draft, verified)

def test_a_declared_percent_unit_admits_when_the_envelope_agrees():
    admitted = _admit(
        _binding({"kind": "declared", "value": _PERCENT}),
        _envelope({"TS_PCT": _PERCENT}), ["TS_PCT"])
    assert admitted.output_bindings[0].value.value == _VALUE

def test_a_declared_unit_that_disagrees_with_the_envelope_still_fails():
    with pytest.raises(ValueError, match="binding unit does not match output authority"):
        _admit(_binding({"kind": "declared", "value": "count"}),
               _envelope({"TS_PCT": _PERCENT}), ["TS_PCT"])

def test_the_catalog_never_overrides_the_unit_the_evidence_declares():
    admitted = _admit(
        _binding({"kind": "declared", "value": _PERCENT}, output_id="N", leaf="n"),
        _envelope({"n": _PERCENT}), ["N"])
    assert admitted.output_bindings[0].value.value == _VALUE

def test_a_closed_capability_still_rejects_catalog_evidence_unit_disagreement():
    with pytest.raises(ValueError, match="catalog and evidence units disagree"):
        _admit(_binding({"kind": "declared", "value": _PERCENT},
                        output_id="NET_RATING", leaf="NET_RATING",
                        domain="team_ratings"),
               _envelope({"NET_RATING": _PERCENT}, capability="team_ratings"),
               ["NET_RATING"], capability="team_ratings")

def test_a_value_the_evidence_does_not_carry_still_fails():
    with pytest.raises(ValueError, match="binding value does not exactly match selected evidence"):
        _admit(_binding({"kind": "declared", "value": _PERCENT}, value=0.71),
               _envelope({"TS_PCT": _PERCENT}), ["TS_PCT"])