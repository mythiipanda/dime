from __future__ import annotations

from datetime import UTC, datetime

import pytest

from v2.adapters.capabilities import CAPABILITIES
from v2.adapters.core import build_envelope
from v2.api.events import BindingDiagnostic, FinalAnswer
from v2.api.sse import _public_payload, encode_event
from v2.contracts import (
    Claim,
    ClaimResult,
    ClaimSource,
    DraftReport,
    EntityRef,
    EvidenceOutputBinding,
    EvidenceRequirement,
    Plan,
    PlanNode,
    SeasonRef,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
    VerifiedClaim,
)
from v2.runtime.loop import _verified_claims
from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings

KNOWN_REJECTION = "binding selector must locate exactly one value"
RUN_ID = "run-" + "a" * 32

def _meta():
    return {
        "source": "warehouse",
        "season": "2024-25",
        "warehouse_id": "frozen-eval",
        "warehouse_sha256": "a" * 64,
    }

def _rows():
    return [
        {
            "TEAM_ID": 1610612738,
            "TEAM_NAME": "Boston Celtics",
            "TEAM": "BOS",
            "GP": 82,
            "W": 61,
            "L": 21,
            "OFF_RATING": 120.0,
            "DEF_RATING": 111.7,
            "NET_RATING": 8.3,
            "PACE": 99.0,
        }
    ]

def _envelope():
    return build_envelope(
        CAPABILITIES["team_ratings"],
        {"season": "2024-25"},
        {"ok": True, "rows": _rows(), "meta": dict(_meta())},
        entities=None,
        observed_at=datetime.now(UTC),
    )

def _task():
    return TaskSpec(
        goal="binding diagnostics probe",
        mode="quick",
        deliverable="answer",
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[EntityRef(id="BOS", type="team", display_name="Boston Celtics")],
        requirements=[
            EvidenceRequirement(
                id="ratings",
                description="binding diagnostics probe",
                capability_options=["team_ratings"],
                requested_outputs=["NET_RATING"],
            )
        ],
    )

def _binding(envelope):
    return EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id="ratings",
        output_id="NET_RATING",
        node_id="ratings",
        evidence_id=envelope.evidence_id,
        selector="rows[5].NET_RATING",
        row_selector="rows[5]",
        value={"kind": "float", "value": 99.9},
        subject_entity_type="team",
        subject_entity_id="BOS",
        subject_selector="rows[5].TEAM_ID",
        unit={"kind": "declared", "value": "points_per_100_possessions"},
        domain="team_ratings",
    )

def _fixtures():
    envelope = _envelope()
    task = _task()
    binding = _binding(envelope)
    node = PlanNode(
        id="ratings",
        description="diagnostics probe",
        capability_hints=[envelope.capability],
        covers_requirement_ids=["ratings"],
        status="complete",
    )
    execution = ExecutionResult(
        plan=Plan(nodes=[node]),
        evidence_by_node={"ratings": envelope},
        attempts={"ratings": 1},
    )
    claim = Claim(
        text="diagnostics probe claim",
        kind="observed",
        evidence_ids=[envelope.evidence_id],
        output_bindings=[binding],
    )
    draft = DraftReport(sections=["probe"], claims=[claim])
    candidate = VerifiedClaim(
        claim_index=0,
        claim=claim,
        evidence_ids=[envelope.evidence_id],
        sources=[
            ClaimSource(
                evidence_id=envelope.evidence_id,
                source=envelope.source,
                capability=envelope.capability,
                observed_at=envelope.observed_at,
            )
        ],
        output_bindings=[binding],
    )
    verification = VerificationReport(
        status=VerificationStatus.PASS,
        claim_results=[ClaimResult(claim_index=0, supported=True)],
    )
    evidence = {envelope.evidence_id: envelope}
    return task, execution, draft, verification, evidence, candidate, envelope

def test_admit_rejects_absent_selector_trio():
    task, execution, draft, verification, evidence, candidate, envelope = _fixtures()
    with pytest.raises(ValueError) as excinfo:
        admit_verified_claim_bindings(task, execution, draft, candidate)
    assert str(excinfo.value) == KNOWN_REJECTION

def test_binding_diagnostic_emitted_when_diagnostics_on():
    task, execution, draft, verification, evidence, candidate, envelope = _fixtures()
    sink = []
    admitted, rejected = _verified_claims(
        task,
        execution,
        draft,
        verification,
        evidence,
        diagnostics=True,
        diagnostics_run_id=RUN_ID,
        diagnostics_events=sink,
    )
    assert len(sink) == 1
    event = sink[0]
    assert isinstance(event, BindingDiagnostic)
    assert event.run_id == RUN_ID
    assert event.claim_index == 0
    assert event.requirement_kind == "evidence"
    assert event.requirement_id == "ratings"
    assert event.output_id == "NET_RATING"
    assert event.node_id == "ratings"
    assert event.evidence_id == envelope.evidence_id
    assert event.selector == "rows[5].NET_RATING"
    assert event.row_selector == "rows[5]"
    assert event.subject_selector == "rows[5].TEAM_ID"
    assert event.subject_entity_type == "team"
    assert event.subject_entity_id == "BOS"
    assert event.declared_value == {"kind": "float", "value": "99.9"}
    assert event.declared_unit == {
        "kind": "declared",
        "value": "points_per_100_possessions",
    }
    assert event.reanchor_changed is False
    assert event.rejection == KNOWN_REJECTION
    assert len(rejected) == 1
    assert KNOWN_REJECTION in rejected[0].message
    assert admitted[0].output_bindings == []

def test_default_path_emits_no_binding_diagnostics():
    task, execution, draft, verification, evidence, candidate, envelope = _fixtures()
    sink = []
    admitted, rejected = _verified_claims(
        task, execution, draft, verification, evidence, diagnostics_events=sink
    )
    assert sink == []
    assert len(rejected) == 1
    assert KNOWN_REJECTION in rejected[0].message

def test_sse_gate_drops_binding_diagnostic_on_default_path():
    event = BindingDiagnostic(
        run_id=RUN_ID,
        claim_index=0,
        requirement_kind="evidence",
        requirement_id="ratings",
        output_id="NET_RATING",
        node_id="ratings",
        evidence_id="ev-1",
        selector="rows[5].NET_RATING",
        row_selector="rows[5]",
        subject_selector="rows[5].TEAM_ID",
        subject_entity_type="team",
        subject_entity_id="BOS",
        declared_value={"kind": "float", "value": "99.9"},
        declared_unit={"kind": "declared", "value": "points_per_100_possessions"},
        reanchor_changed=False,
        rejection=KNOWN_REJECTION,
    )
    assert _public_payload(event) is None
    assert encode_event(event) is None
    opened = _public_payload(event, diagnostics=True)
    assert opened["rejection"] == KNOWN_REJECTION
    assert opened["selector"] == "rows[5].NET_RATING"
    wire = encode_event(event, diagnostics=True)
    assert wire.startswith("event: binding_diagnostic\n")
    assert KNOWN_REJECTION in wire

def test_final_answer_contract_unchanged_by_diagnostics_flag():
    answer = FinalAnswer(
        text="Some requested outputs could not be published.",
        carry={"run_id": RUN_ID},
    )
    assert encode_event(answer) == encode_event(answer, diagnostics=True)
    assert KNOWN_REJECTION not in encode_event(answer)

def test_routes_guard_keeps_default_stream_clean():
    from types import SimpleNamespace

    from v2.api.routes import _stream_binding_diagnostics

    result = SimpleNamespace(
        binding_diagnostics=[
            {
                "run_id": RUN_ID,
                "claim_index": 0,
                "requirement_kind": "evidence",
                "requirement_id": "ratings",
                "output_id": "NET_RATING",
                "node_id": "ratings",
                "evidence_id": "ev-1",
                "selector": "rows[5].NET_RATING",
                "row_selector": "rows[5]",
                "subject_selector": "rows[5].TEAM_ID",
                "subject_entity_type": "team",
                "subject_entity_id": "BOS",
                "declared_value": {"kind": "float", "value": "99.9"},
                "declared_unit": {
                    "kind": "declared",
                    "value": "points_per_100_possessions",
                },
                "reanchor_changed": False,
                "rejection": KNOWN_REJECTION,
            }
        ]
    )
    assert _stream_binding_diagnostics(result, False) == []
    chunks = _stream_binding_diagnostics(result, True)
    assert len(chunks) == 1
    assert "binding_diagnostic" in chunks[0]
    assert KNOWN_REJECTION in chunks[0]
