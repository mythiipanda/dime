from datetime import datetime

import pytest
from pydantic import ValidationError

from v2.contracts import (
    Claim,
    ClaimKind,
    DraftReport,
    EvidenceEnvelope,
    Plan,
    PlanNode,
    TaskSpec,
    EntityRef,
)


def test_plan_accepts_dag():
    plan = Plan(nodes=[
        PlanNode(id="baseline", description="Get baseline"),
        PlanNode(id="report", description="Write report",
                 depends_on=["baseline"]),
    ])
    assert plan.nodes[1].depends_on == ["baseline"]


def test_plan_rejects_cycle():
    with pytest.raises(ValidationError, match="acyclic"):
        Plan(nodes=[
            PlanNode(id="a", description="A", depends_on=["b"]),
            PlanNode(id="b", description="B", depends_on=["a"]),
        ])


def test_claim_support_rules():
    with pytest.raises(ValidationError, match="require evidence"):
        Claim(text="Boston won 60 games", kind=ClaimKind.OBSERVED)
    claim = Claim(text="Boston projects to 55 wins", kind=ClaimKind.PROJECTION,
                  confidence=0.6, evidence_ids=["baseline"])
    assert claim.confidence == 0.6


def test_evidence_round_trip():
    evidence = EvidenceEnvelope(
        evidence_id="ratings:bos:2025-26",
        capability="team_ratings",
        source="warehouse:silver_team_ratings",
        observed_at=datetime(2026, 9, 14, 14, 0),
        season="2025-26",
        rows=[{"TEAM": "BOS", "NET_RATING": 8.2}],
        units={"NET_RATING": "points per 100 possessions"},
    )
    assert EvidenceEnvelope.model_validate_json(
        evidence.model_dump_json()).rows[0]["TEAM"] == "BOS"


def test_task_scope_rejects_duplicate_contract_entries() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="required_evidence"):
        TaskSpec(goal="record", mode="quick", deliverable="answer",
                 required_evidence=["standings", "standings"])
    with pytest.raises(ValidationError, match="duplicate identities"):
        TaskSpec(goal="record", mode="quick", deliverable="answer",
                 entities=[
                     EntityRef(id="BOS", type="team", display_name="Boston"),
                     EntityRef(id="BOS", type="team", display_name="Celtics"),
                 ])
    with pytest.raises(ValidationError, match="skills"):
        TaskSpec(goal="trade", mode="deep_dive", deliverable="analysis",
                 skills=["trade-analysis", "trade-analysis"])


def test_plan_node_exposes_only_enforced_execution_contract() -> None:
    assert "expected_schema" not in PlanNode.model_fields
    assert "completion_test" not in PlanNode.model_fields


def test_plan_node_rejects_unenforced_model_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PlanNode(
            id="facts",
            description="facts",
            expected_schema={"wins": "integer"},
        )


@pytest.mark.parametrize("model,payload", [
    (TaskSpec, {"goal": "record", "mode": "quick", "deliverable": "answer",
                "invented_scope": "ignored"}),
    (Plan, {"nodes": [], "invented_node_group": []}),
    (Claim, {"text": "Judgment.", "kind": "judgment",
             "invented_citation": "ev"}),
])
def test_model_authored_contracts_reject_unknown_fields(model, payload) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model.model_validate(payload)


@pytest.mark.parametrize("payload,error", [
    ({"status": "pass", "missing_branches": ["salary"]}, "pass status contradicts"),
    ({"status": "repair"}, "repair status requires"),
])
def test_verification_status_must_match_findings(payload, error) -> None:
    from v2.contracts import VerificationReport

    with pytest.raises(ValidationError, match=error):
        VerificationReport.model_validate(payload)


def test_unsupported_claim_result_requires_a_reason() -> None:
    from v2.contracts import ClaimResult

    with pytest.raises(ValidationError, match="requires a reason"):
        ClaimResult(claim_index=0, supported=False)


@pytest.mark.parametrize("payload,error", [
    ({"text": "Observed.", "kind": "observed", "evidence_ids": ["ev", "ev"]},
     "must not contain duplicates"),
    ({"text": "Observed.", "kind": "observed", "evidence_ids": ["ev"],
      "calculation_id": "calc"}, "only derived"),
    ({"text": "Judgment.", "kind": "judgment", "confidence": 0.8},
     "only projection"),
])
def test_claim_kind_rejects_inapplicable_or_duplicate_support(payload, error) -> None:
    with pytest.raises(ValidationError, match=error):
        Claim.model_validate(payload)


@pytest.mark.parametrize("field,value", [
    ("goal", "  "),
    ("deliverable", ""),
    ("subquestions", ["role", "role"]),
    ("assumptions", [""]),
    ("open_questions", ["which season?", "which season?"]),
])
def test_task_scope_rejects_empty_or_duplicate_semantics(field, value) -> None:
    payload = {"goal": "record", "mode": "quick", "deliverable": "answer",
               field: value}
    with pytest.raises(ValidationError, match=field):
        TaskSpec.model_validate(payload)


@pytest.mark.parametrize("payload,error", [
    ({"id": " ", "description": "facts"}, "non-empty"),
    ({"id": "facts", "description": " "}, "non-empty"),
    ({"id": "facts", "description": "facts", "depends_on": ["a", "a"]},
     "dependencies must not contain duplicates"),
    ({"id": "facts", "description": "facts", "capability_hints": ["x", "x"]},
     "capability hints must not contain duplicates"),
])
def test_plan_node_rejects_ambiguous_identity_or_selection(payload, error) -> None:
    with pytest.raises(ValidationError, match=error):
        PlanNode.model_validate(payload)


@pytest.mark.parametrize("payload,error", [
    ({"sections": ["Answer", "Answer"], "claims": [], "gaps": ["missing"]},
     "sections must not contain duplicates"),
    ({"sections": [], "claims": [], "gaps": [""]},
     "gaps must not contain empty values"),
])
def test_draft_report_rejects_empty_or_duplicate_content(payload, error) -> None:
    with pytest.raises(ValidationError, match=error):
        DraftReport.model_validate(payload)


@pytest.mark.parametrize("payload,error", [
    ({"status": "partial", "claim_results": [
        {"claim_index": 0, "supported": True},
        {"claim_index": 0, "supported": True},
    ]}, "claim indices must be unique"),
    ({"status": "partial", "missing_branches": ["salary", "salary"]},
     "missing_branches must not contain duplicates"),
    ({"status": "partial", "contradictions": [""]},
     "contradictions must not contain empty values"),
])
def test_verification_report_rejects_duplicate_or_empty_findings(payload, error) -> None:
    from v2.contracts import VerificationReport

    with pytest.raises(ValidationError, match=error):
        VerificationReport.model_validate(payload)


@pytest.mark.parametrize("payload,error", [
    ({"kind": "missing_evidence", "message": " ", "blocks": []},
     "message must be non-empty"),
    ({"kind": "missing_evidence", "message": "missing", "blocks": ["x", "x"]},
     "blocks must not contain duplicates"),
])
def test_gap_rejects_empty_or_duplicate_references(payload, error) -> None:
    from v2.contracts import Gap

    with pytest.raises(ValidationError, match=error):
        Gap.model_validate(payload)


def test_claim_result_rejects_duplicate_reasons() -> None:
    from v2.contracts import ClaimResult

    with pytest.raises(ValidationError, match="reasons must not contain duplicates"):
        ClaimResult(claim_index=0, supported=False, reasons=["bad", "bad"])


def test_claim_source_and_verified_claim_reject_ambiguous_identity() -> None:
    from v2.contracts import ClaimSource, VerifiedClaim

    with pytest.raises(ValidationError, match="source identity must be non-empty"):
        ClaimSource(evidence_id="ev", source=" ", capability="standings")
    claim = Claim(text="Observed.", kind="observed", evidence_ids=["ev"])
    with pytest.raises(ValidationError, match="evidence_ids must not contain duplicates"):
        VerifiedClaim(claim_index=0, claim=claim, evidence_ids=["ev", "ev"])


def test_entity_and_season_identity_must_be_non_empty() -> None:
    from v2.contracts import SeasonRef

    with pytest.raises(ValidationError, match="entity id and display name"):
        EntityRef(id="BOS", type="team", display_name=" ")
    with pytest.raises(ValidationError, match="season value must be non-empty"):
        SeasonRef(value=" ", source="user", confidence=1)


def test_projection_requires_scenario_evidence() -> None:
    with pytest.raises(ValidationError, match="projection claims require evidence"):
        Claim(text="Boston projects to improve.", kind="projection", confidence=0.6)
