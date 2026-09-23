from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from v2.contracts import (
    Claim,
    ClaimResult,
    ClaimKind,
    DraftReport,
    EvidenceEnvelope,
    Plan,
    PlanNode,
    TaskSpec,
    SeasonRef,
    VerificationReport,
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
        observed_at=datetime(2026, 9, 14, 14, 0, tzinfo=UTC),
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


def test_supported_claim_result_rejects_rejection_reasons() -> None:
    from v2.contracts import ClaimResult

    with pytest.raises(ValidationError, match="cannot carry rejection reasons"):
        ClaimResult(claim_index=0, supported=True, reasons=["maybe"])


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


@pytest.mark.parametrize("value", [
    float("nan"), float("inf"), float("-inf"),
    {"nested": [1, float("nan")]},
])
def test_plan_node_rejects_nonfinite_arguments(value) -> None:
    with pytest.raises(ValidationError, match="arguments must contain only finite"):
        PlanNode(id="facts", description="facts", arguments={"value": value})


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


@pytest.mark.parametrize("payload,error", [
    ({"text": " ", "kind": "judgment"}, "claim text must be non-empty"),
    ({"text": "Observed.", "kind": "observed", "evidence_ids": [""]},
     "evidence_ids must not contain empty values"),
])
def test_claim_rejects_empty_text_or_evidence_identity(payload, error) -> None:
    with pytest.raises(ValidationError, match=error):
        Claim.model_validate(payload)


def test_verified_claim_requires_exact_source_binding() -> None:
    from v2.contracts import ClaimSource, VerifiedClaim

    claim = Claim(text="Observed.", kind="observed", evidence_ids=["ev"])
    source = ClaimSource(evidence_id="ev", source="fixture", capability="standings")
    VerifiedClaim(claim_index=0, claim=claim, evidence_ids=["ev"], sources=[source])
    with pytest.raises(ValidationError, match="evidence must match"):
        VerifiedClaim(claim_index=0, claim=claim, evidence_ids=[], sources=[])
    unknown = ClaimSource(evidence_id="other", source="fixture", capability="standings")
    with pytest.raises(ValidationError, match="belong to its evidence"):
        VerifiedClaim(claim_index=0, claim=claim, evidence_ids=["ev"], sources=[unknown])


def test_conversation_turn_rejects_blank_content() -> None:
    from pydantic import ValidationError
    from v2.contracts import ConversationTurn

    with pytest.raises(ValidationError, match="content must be non-empty"):
        ConversationTurn(role="user", content=" ")


@pytest.mark.parametrize("changes,error", [
    ({"evidence_id": " "}, "evidence identity"),
    ({"season": " "}, "evidence season"),
    ({"qualification": " "}, "evidence qualification"),
    ({"coverage": " "}, "evidence coverage"),
])
def test_evidence_rejects_blank_optional_metadata(changes, error) -> None:
    payload = {"evidence_id": "ev", "capability": "standings",
               "source": "fixture", "observed_at": datetime(2026, 9, 15, tzinfo=UTC),
               "rows": {}}
    payload.update(changes)
    with pytest.raises(ValidationError, match=error):
        EvidenceEnvelope.model_validate(payload)


def test_derived_claim_rejects_blank_calculation_identity() -> None:
    with pytest.raises(ValidationError, match="non-empty calculation id"):
        Claim(text="Derived.", kind="derived", evidence_ids=["ev"],
              calculation_id=" ")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_evidence_rejects_nonfinite_row_values(value) -> None:
    with pytest.raises(ValidationError, match="only finite numbers"):
        EvidenceEnvelope(
            evidence_id="ev", capability="ratings", source="fixture",
            observed_at=datetime(2026, 9, 15, tzinfo=UTC), rows={"rating": value})


@pytest.mark.parametrize("value", ["2025", "25-26", "2025-27", "2025/26"])
def test_season_ref_requires_consecutive_canonical_format(value) -> None:
    from v2.contracts import SeasonRef
    with pytest.raises(ValidationError, match="consecutive YYYY-YY"):
        SeasonRef(value=value, source="user", confidence=1)


def test_evidence_season_requires_canonical_format() -> None:
    with pytest.raises(ValidationError, match="consecutive YYYY-YY"):
        EvidenceEnvelope(
            evidence_id="ev", capability="standings", source="fixture",
            observed_at=datetime(2026, 9, 15, tzinfo=UTC), season="2025-27", rows={})


def test_evidence_contract_requires_timezone_aware_observation_time() -> None:
    from datetime import datetime
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="observed_at must include timezone"):
        EvidenceEnvelope(
            evidence_id="ev", capability="standings", source="fixture",
            observed_at=datetime(2026, 9, 15), rows={"wins": 61},
        )


def test_evidence_rejects_tzinfo_without_utc_offset() -> None:
    from datetime import datetime, tzinfo

    class MissingOffset(tzinfo):
        def utcoffset(self, dt):
            return None

    with pytest.raises(ValidationError, match="observed_at must include timezone"):
        EvidenceEnvelope(
            evidence_id="ev", capability="standings", source="fixture",
            observed_at=datetime(2026, 9, 15, tzinfo=MissingOffset()), rows={},
        )


@pytest.mark.parametrize("schema,payload", [
    (EvidenceEnvelope, {"evidence_id": "ev", "capability": "test",
     "source": "fixture", "observed_at": "2026-09-15T00:00:00Z",
     "rows": {}, "task_season_scoped": "false"}),
    (ClaimResult, {"claim_index": 0, "supported": "false", "reasons": ["bad"]}),
])
def test_truth_bearing_contract_flags_are_strict(schema, payload) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


@pytest.mark.parametrize("schema,payload", [
    (PlanNode, {"id": "node", "description": "work", "max_attempts": True}),
    (ClaimResult, {"claim_index": "0", "supported": False, "reasons": ["bad"]}),
])
def test_execution_coordinates_are_strict_integers(schema, payload) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


@pytest.mark.parametrize("schema,payload", [
    (SeasonRef, {"value": "2025-26", "source": "user", "confidence": "1"}),
    (Claim, {"text": "Boston projects higher.", "kind": "projection",
             "confidence": True, "evidence_ids": ["ev"]}),
])
def test_confidence_values_are_strict_floats(schema, payload) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


def test_plan_has_a_hard_execution_node_limit() -> None:
    with pytest.raises(ValidationError, match="at most 32 items"):
        Plan(nodes=[
            PlanNode(id=f"node-{index}", description="work")
            for index in range(33)
        ])


@pytest.mark.parametrize("field_name,limit", [
    ("subquestions", 32), ("required_evidence", 32),
    ("assumptions", 32), ("open_questions", 32), ("skills", 16),
])
def test_task_scope_lists_have_hard_limits(field_name, limit) -> None:
    with pytest.raises(ValidationError, match=f"at most {limit} items"):
        TaskSpec(goal="answer", mode="quick", deliverable="text",
                 **{field_name: [f"value-{index}" for index in range(limit + 1)]})


def test_plan_node_selection_lists_have_hard_limits() -> None:
    with pytest.raises(ValidationError, match="at most 16 items"):
        PlanNode(id="node", description="work",
                 capability_hints=[f"cap-{index}" for index in range(17)])


def test_draft_and_verification_lists_have_hard_limits() -> None:
    with pytest.raises(ValidationError, match="at most 32 items"):
        DraftReport(sections=[f"section-{index}" for index in range(33)], claims=[])
    with pytest.raises(ValidationError, match="at most 128 items"):
        VerificationReport(
            status="repair",
            repair_instructions=[f"repair-{index}" for index in range(129)],
        )


def test_evidence_lineage_and_warning_lists_have_hard_limits() -> None:
    base = {"evidence_id": "ev", "capability": "test", "source": "fixture",
            "observed_at": "2026-09-15T00:00:00Z", "rows": {}}
    with pytest.raises(ValidationError, match="at most 32 items"):
        EvidenceEnvelope(**base, lineage=[f"ev-{index}" for index in range(33)])
    with pytest.raises(ValidationError, match="at most 64 items"):
        EvidenceEnvelope(**base, warnings=[f"warning-{index}" for index in range(65)])


def test_plan_argument_map_has_a_hard_limit() -> None:
    with pytest.raises(ValidationError, match="at most 64 items"):
        PlanNode(id="node", description="work",
                 arguments={f"key-{index}": index for index in range(65)})


def test_core_text_contracts_have_hard_limits() -> None:
    with pytest.raises(ValidationError, match="at most 2000 characters"):
        TaskSpec(goal="x" * 2001, mode="quick", deliverable="text")
    with pytest.raises(ValidationError, match="at most 4000 characters"):
        Claim(text="x" * 4001, kind="opinion")


def test_evidence_optional_metadata_text_has_hard_limits() -> None:
    with pytest.raises(ValidationError, match="at most 4000 characters"):
        EvidenceEnvelope(evidence_id="ev", capability="test", source="fixture",
                         observed_at="2026-09-15T00:00:00Z", rows={},
                         coverage="x" * 4001)


def test_source_identity_is_typed_frozen_and_does_not_change_evidence_id():
    from datetime import UTC,datetime
    from v2.contracts import EvidenceEnvelope
    base=dict(evidence_id='stable',capability='x',source='fixture',observed_at=datetime.now(UTC),rows=[])
    plain=EvidenceEnvelope(**base);bound=EvidenceEnvelope(**base,source_identity={'kind':'warehouse','warehouse_id':'frozen-eval','sha256':'a'*64})
    assert plain.evidence_id==bound.evidence_id=='stable' and bound.lineage==[]
    for bad in [
      {'kind':'warehouse','warehouse_id':'frozen-eval','sha256':'BAD'},
      {'kind':'unknown'},
      {'kind':'live','source':'https://private','extra':'x'}]:
        with pytest.raises(Exception):EvidenceEnvelope(**base,source_identity=bad)


def test_generated_evidence_id_unchanged_by_source_identity():
    from datetime import UTC,datetime
    from v2.adapters.capabilities import CAPABILITIES
    from v2.adapters.core import build_envelope
    result={'ok':True,'rows':[{'TEAM_NAME':'A'}],'meta':{'source':'nba_api','season':'2025-26'}}
    plain=build_envelope(CAPABILITIES['team_ratings'],{'season':'2025-26'},result,observed_at=datetime.now(UTC))
    bound=build_envelope(CAPABILITIES['team_ratings'],{'season':'2025-26'},{'ok':True,'rows':[{'TEAM_NAME':'A'}],'meta':{'source':'nba_api','season':'2025-26','warehouse_id':'frozen-eval','warehouse_sha256':'a'*64}},observed_at=plain.observed_at)
    assert plain.evidence_id==bound.evidence_id
    assert bound.source_identity.model_dump()=={'kind':'warehouse','warehouse_id':'frozen-eval','sha256':'a'*64}

@pytest.mark.parametrize('meta',[{'warehouse_id':'frozen-eval'},{'warehouse_sha256':'a'*64},{'warehouse_id':'frozen-eval','warehouse_sha256':'a'*64,'lineage_kind':'live','source':'nba_api'}])
def test_build_envelope_rejects_partial_or_conflicting_source_markers(meta):
    from v2.adapters.capabilities import CAPABILITIES
    from v2.adapters.core import build_envelope,AdapterError
    with pytest.raises(AdapterError):build_envelope(CAPABILITIES['team_ratings'],{}, {'ok':True,'rows':[],'meta':meta})

def test_build_envelope_maps_explicit_live_source_identity():
    from v2.adapters.capabilities import CAPABILITIES
    from v2.adapters.core import build_envelope
    item=build_envelope(CAPABILITIES['team_ratings'],{}, {'ok':True,'rows':[],'meta':{'lineage_kind':'live','source':'nba_api'}})
    assert item.source_identity.model_dump()=={'kind':'live','source':'nba_api'}

@pytest.mark.parametrize('meta',[
 {'warehouse_id':'','warehouse_sha256':''},
 {'warehouse_id':'','warehouse_sha256':'a'*64},
 {'warehouse_id':'frozen-eval','warehouse_sha256':''},
 {'warehouse_id':'unknown','warehouse_sha256':'a'*64},
 {'warehouse_id':'frozen-eval','warehouse_sha256':'BAD'},
 {'warehouse_id':'frozen-eval','warehouse_sha256':'A'*64},
 {'warehouse_id':''}, {'lineage_kind':'unknown'},
 {'lineage_kind':'live','source':'nba_api','warehouse_id':'','warehouse_sha256':''},
])
def test_build_envelope_rejects_empty_or_unknown_provenance_markers(meta):
    from v2.adapters.capabilities import CAPABILITIES
    from v2.adapters.core import build_envelope,AdapterError
    with pytest.raises(AdapterError,match='source identity|source identity kind'):
        build_envelope(CAPABILITIES['team_ratings'],{}, {'ok':True,'rows':[],'meta':meta})


def test_bare_display_source_is_not_inferred_as_live_provenance():
    from v2.adapters.capabilities import CAPABILITIES
    from v2.adapters.core import build_envelope
    item=build_envelope(CAPABILITIES['team_ratings'],{}, {'ok':True,'rows':[],'meta':{'source':'nba_api'}})
    assert item.source=='v1:get_ratings:nba_api' and item.source_identity is None



def _admission_target(seed: str = "a"):
    from v2.contracts import AdmissionReviewTarget
    return AdmissionReviewTarget(
        request_sha256=seed * 64, context_sha256="b" * 64,
        task_sha256="c" * 64)


def _entity_subject(entity_id: str = "2544", entity_type: str = "player"):
    from v2.contracts import EntityAdmissionSubject
    return EntityAdmissionSubject(
        kind="entity", entity_id=entity_id, entity_type=entity_type)


def _locator(text: str = "LeBron James", start: int = 8):
    from v2.contracts import SourceLocator
    return SourceLocator(source="request", start=start,
                         end=start + len(text), text=text)


def test_source_locator_is_exact_frozen_and_source_typed():
    from v2.contracts import SourceLocator
    request = _locator()
    with pytest.raises(ValidationError, match="frozen"):
        request.start = 0
    with pytest.raises(ValidationError, match="context turn"):
        SourceLocator(source="request", context_turn=0, start=0, end=1, text="x")
    with pytest.raises(ValidationError, match="requires a context turn"):
        SourceLocator(source="context", start=0, end=1, text="x")
    with pytest.raises(ValidationError, match="offsets must match"):
        SourceLocator(source="request", start=0, end=2, text="x")


def test_review_target_is_frozen_and_rejects_noncanonical_digests():
    target = _admission_target()
    with pytest.raises(ValidationError, match="frozen"):
        target.task_sha256 = "d" * 64
    with pytest.raises(ValidationError):
        _admission_target("A")


def test_intake_admission_review_rejects_empty_or_incomplete_admit():
    from v2.contracts import AdmissionBinding, IntakeAdmissionReview
    subject = _entity_subject()
    with pytest.raises(ValidationError, match="at least 1 item"):
        IntakeAdmissionReview(target=_admission_target(), decision="admit",
                              expected_subjects=[])
    with pytest.raises(ValidationError, match="bind every expected subject"):
        IntakeAdmissionReview(target=_admission_target(), decision="admit",
                              expected_subjects=[subject])
    admitted = IntakeAdmissionReview(
        target=_admission_target(), decision="admit",
        expected_subjects=[subject],
        bindings=[AdmissionBinding(subject=subject, locator=_locator())])
    assert admitted.decision == "admit"


def test_admission_review_cannot_be_replayed_for_another_target():
    from v2.contracts import AdmissionBinding, IntakeAdmissionReview
    subject = _entity_subject()
    review = IntakeAdmissionReview(
        target=_admission_target("a"), decision="admit",
        expected_subjects=[subject],
        bindings=[AdmissionBinding(subject=subject, locator=_locator())])
    review.require_target(_admission_target("a"))
    with pytest.raises(ValueError, match="target does not match"):
        review.require_target(_admission_target("d"))


def test_block_requires_typed_finding_or_unresolved_reference():
    from v2.contracts import AdmissionFinding, IntakeAdmissionReview
    subject = _entity_subject()
    with pytest.raises(ValidationError, match="typed blocker"):
        IntakeAdmissionReview(target=_admission_target(), decision="block",
                              expected_subjects=[subject])
    with pytest.raises(ValidationError, match="affected subject"):
        AdmissionFinding(code="subject_mismatch")
    blocked = IntakeAdmissionReview(
        target=_admission_target(), decision="block",
        expected_subjects=[subject], findings=[AdmissionFinding(
            code="subject_mismatch", affected_subjects=[subject])])
    assert blocked.findings[0].code == "subject_mismatch"



def test_season_admission_subject_reuses_canonical_season_invariant():
    from v2.contracts import SeasonAdmissionSubject
    assert SeasonAdmissionSubject(kind="season", value="2025-26").value == "2025-26"
    for value in ("2025-24", "2025-99", "2025-27", "25-26"):
        with pytest.raises(ValidationError, match="consecutive YYYY-YY"):
            SeasonAdmissionSubject(kind="season", value=value)


def test_unresolved_block_requires_source_bound_unresolved_reference():
    from v2.contracts import (IntakeAdmissionReview, SourceLocator,
                              UnresolvedReference)
    subject = _entity_subject()
    with pytest.raises(ValidationError):
        # `unresolved_reference` is intentionally not a finding code: a code
        # without a source locator cannot establish an unresolved referent.
        IntakeAdmissionReview(
            target=_admission_target(), decision="block",
            expected_subjects=[subject],
            findings=[{"code": "unresolved_reference"}])
    locator = SourceLocator(source="request", start=0, end=2, text="he")
    blocked = IntakeAdmissionReview(
        target=_admission_target(), decision="block",
        expected_subjects=[subject], unresolved_references=[
            UnresolvedReference(kind="player", locator=locator)])
    assert blocked.unresolved_references[0].locator == locator

def test_explicit_lebron_fixture_binds_complete_typed_subject_manifest():
    from v2.contracts import (AdmissionBinding, EntityAdmissionSubject,
        IntakeAdmissionReview, OutputAdmissionSubject,
        RequirementAdmissionSubject, SourceLocator)
    request = "Analyze LeBron James with the Philadelphia 76ers for fit."
    subjects = [
        EntityAdmissionSubject(kind="entity", entity_id="2544", entity_type="player"),
        EntityAdmissionSubject(kind="entity", entity_id="1610612755", entity_type="team"),
        RequirementAdmissionSubject(kind="requirement", requirement_kind="evidence", requirement_id="fit"),
        OutputAdmissionSubject(kind="output", owner_kind="evidence", requirement_id="fit", output_id="FIT_ASSESSMENT"),
    ]
    texts = ["LeBron James", "Philadelphia 76ers", "fit", "fit"]
    bindings = []
    for subject, text in zip(subjects, texts, strict=True):
        start = request.index(text)
        bindings.append(AdmissionBinding(
            subject=subject, locator=SourceLocator(
                source="request", start=start, end=start + len(text), text=text)))
    review = IntakeAdmissionReview(
        target=_admission_target(), decision="admit",
        expected_subjects=subjects, bindings=bindings)
    assert review.unresolved_references == ()
    assert len(review.bindings) == len(review.expected_subjects) == 4


def test_unicode_and_punctuation_remain_verbatim_in_source_locator():
    from v2.contracts import SourceLocator
    request = "Compare Nikola Jokić’s impact."
    text = "Nikola Jokić’s"
    start = request.index(text)
    locator = SourceLocator(source="request", start=start,
                            end=start + len(text), text=text)
    assert locator.text == request[locator.start:locator.end]


def test_composite_warehouse_identity_is_typed_and_complete():
    from datetime import UTC, datetime
    from v2.adapters.capabilities import CAPABILITIES
    from v2.adapters.core import build_envelope
    item = build_envelope(CAPABILITIES["injury_impact"], {"season": "2025-26"}, {
        "ok": True, "rows": {"impact": "unknown"},
        "meta": {"source": "espn+nba_api+warehouse", "season": "2025-26",
                 "warehouse_id": "configured-runtime", "warehouse_sha256": "a" * 64}},
        observed_at=datetime.now(UTC))
    assert item.source_identity.model_dump() == {
        "kind": "composite", "warehouse_id": "configured-runtime",
        "sha256": "a" * 64, "live_sources": ["espn", "nba_api"]}
