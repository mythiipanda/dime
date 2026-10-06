from v2.contracts import (
    Claim, ClaimResult, DraftReport, VerificationReport,
)
from v2.runtime.loop import _verification_gaps, _verified_claims
from v2.runtime.models import ExecutionResult
from v2.contracts import Plan, PlanNode, TaskSpec


def verified(draft, report, evidence=None):
    evidence = evidence or {}
    plan = Plan(nodes=[PlanNode(id=f"n{index}", description="facts",
        capability_hints=[item.capability], status="complete")
        for index, item in enumerate(evidence.values())])
    execution = ExecutionResult(plan=plan,
        evidence_by_node={f"n{index}": item
                          for index, item in enumerate(evidence.values())},
        attempts={f"n{index}": 1 for index in range(len(evidence))})
    claims, gaps = _verified_claims(
        TaskSpec(goal="g", mode="quick", deliverable="d"),
        execution, draft, report, evidence)
    assert gaps == []
    return claims


def test_adjudication_keeps_model_prose_and_marks_supported_claims():
    draft = DraftReport(sections=["Answer"], claims=[
        Claim(text="Boston won 61 games.", kind="observed", evidence_ids=["ev"]),
        Claim(text="Boston won 62 games.", kind="observed", evidence_ids=["ev"]),
    ])
    report = VerificationReport(status="partial", claim_results=[
        ClaimResult(claim_index=0, supported=True),
        ClaimResult(claim_index=1, supported=False, reasons=["uncited numeral 62"]),
    ])
    claims = verified(draft, report)
    assert [item.claim.text for item in claims] == ["Boston won 61 games."]
    assert claims[0].evidence_ids == ["ev"]
    gaps = _verification_gaps(draft, report)
    assert gaps[0].kind == "unsupported_claim"
    assert gaps[0].evidence_ids == ["ev"]
    assert gaps[0].blocks == ["claim:1"]


def test_verified_claim_carries_per_claim_provenance_for_mixed_sources():
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope

    draft = DraftReport(sections=["Comparison"], claims=[
        Claim(text="SGA scored 31.1 PPG.", kind="observed",
              evidence_ids=["warehouse-sga"]),
        Claim(text="Luka scored 33.5 PPG.", kind="observed",
              evidence_ids=["fallback-luka"]),
    ])
    report = VerificationReport(status="pass", claim_results=[
        ClaimResult(claim_index=0, supported=True),
        ClaimResult(claim_index=1, supported=True),
    ])
    evidence = {
        "warehouse-sga": EvidenceEnvelope(
            evidence_id="warehouse-sga", capability="player_report",
            source="warehouse:silver_player_season", observed_at=datetime.now(UTC),
            rows={"player": "SGA", "ppg": 31.1}),
        "fallback-luka": EvidenceEnvelope(
            evidence_id="fallback-luka", capability="player_report",
            source="fallback:basketball-reference", observed_at=datetime.now(UTC),
            rows={"player": "Luka", "ppg": 33.5}),
    }
    claims = verified(draft, report, evidence)
    assert claims[0].sources[0].source.startswith("warehouse:")
    assert claims[1].sources[0].source.startswith("fallback:")
    assert claims[0].sources != claims[1].sources


def test_execution_errors_surface_as_typed_gaps() -> None:
    draft = DraftReport(sections=["Trade"], claims=[])
    report = VerificationReport(status="partial")
    gaps = _verification_gaps(
        draft, report,
        {"salary": ["AdapterError: cap ledger unavailable"]},
    )
    assert len(gaps) == 1
    assert gaps[0].kind == "execution_failure"
    assert gaps[0].message == "execution failed for salary"
    assert gaps[0].blocks == ["node:salary"]


def test_pass_status_without_claim_adjudication_publishes_nothing() -> None:
    draft = DraftReport(sections=["Answer"], claims=[
        Claim(text="Boston won 61 games.", kind="observed", evidence_ids=["ev"]),
    ])
    report = VerificationReport(status="pass", claim_results=[])
    assert verified(draft, report) == []


def test_runtime_result_rejects_mismatched_verified_claim() -> None:
    import pytest
    from pydantic import ValidationError
    from v2.contracts import VerifiedClaim
    from v2.runtime.models import ExecutionResult, RuntimeResult
    from v2.contracts import Plan, TaskSpec

    draft = DraftReport(sections=["Answer"], claims=[
        Claim(text="Boston won 61 games.", kind="observed", evidence_ids=["ev"]),
    ])
    report = VerificationReport(status="partial", claim_results=[
        ClaimResult(claim_index=0, supported=False, reasons=["unsupported"]),
    ])
    with pytest.raises(ValidationError, match="lacks supported adjudication"):
        RuntimeResult(
            task=TaskSpec(goal="record", mode="quick", deliverable="answer"),
            execution=ExecutionResult(plan=Plan(nodes=[])),
            draft=draft, verification=report,
            verified_claims=[VerifiedClaim(
                claim_index=0, claim=draft.claims[0], evidence_ids=["ev"]),
            ],
        )


def test_runtime_result_rejects_forged_claim_source() -> None:
    import pytest
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.contracts import ClaimSource, EvidenceEnvelope, Plan, PlanNode, TaskSpec, VerifiedClaim
    from v2.runtime.models import ExecutionResult, RuntimeResult

    claim = Claim(text="Boston won 61 games.", kind="observed", evidence_ids=["ev"])
    with pytest.raises(ValidationError, match="sources do not match"):
        RuntimeResult(
            task=TaskSpec(goal="record", mode="quick", deliverable="answer"),
            execution=ExecutionResult(
                plan=Plan(nodes=[PlanNode(
                    id="facts", description="facts", capability_hints=["standings"],
                    status="complete")]),
                evidence_by_node={"facts": EvidenceEnvelope(
                    evidence_id="ev", capability="standings",
                    source="warehouse:standings", observed_at=datetime.now(UTC),
                    rows={"wins": 61},
                )},
                attempts={"facts": 1},
            ),
            draft=DraftReport(sections=["Answer"], claims=[claim]),
            verification=VerificationReport(status="pass", claim_results=[
                ClaimResult(claim_index=0, supported=True),
            ]),
            verified_claims=[VerifiedClaim(
                claim_index=0, claim=claim, evidence_ids=["ev"],
                sources=[ClaimSource(
                    evidence_id="ev", source="web:forged",
                    capability="standings")],
            )],
        )


def test_runtime_result_rejects_verified_claim_with_unknown_execution_evidence() -> None:
    import pytest
    from pydantic import ValidationError
    from v2.contracts import Plan, TaskSpec, VerifiedClaim
    from v2.runtime.models import ExecutionResult, RuntimeResult

    claim = Claim(text="Boston won 61 games.", kind="observed",
                  evidence_ids=["invented"])
    draft = DraftReport(sections=["Answer"], claims=[claim])
    with pytest.raises(ValidationError, match="verified claim cites unknown execution evidence"):
        RuntimeResult(
            task=TaskSpec(goal="record", mode="quick", deliverable="answer"),
            execution=ExecutionResult(plan=Plan(nodes=[])),
            draft=draft,
            verification=VerificationReport(status="pass", claim_results=[
                ClaimResult(claim_index=0, supported=True),
            ]),
            verified_claims=[VerifiedClaim(
                claim_index=0, claim=claim, evidence_ids=["invented"]
            )],
        )


def test_runtime_result_rejects_gap_with_unknown_evidence() -> None:
    import pytest
    from pydantic import ValidationError
    from v2.contracts import Gap, Plan, TaskSpec
    from v2.runtime.models import ExecutionResult, RuntimeResult

    with pytest.raises(ValidationError, match="gap cites unknown evidence"):
        RuntimeResult(
            task=TaskSpec(goal="record", mode="quick", deliverable="answer"),
            execution=ExecutionResult(plan=Plan(nodes=[])),
            draft=DraftReport(sections=[], claims=[]),
            verification=VerificationReport(status="partial"),
            gaps=[Gap(kind="source_conflict", message="conflict",
                      evidence_ids=["invented"])],
        )


def test_empty_execution_evidence_becomes_a_cited_typed_gap() -> None:
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.loop import _empty_evidence_gaps

    empty = EvidenceEnvelope(
        evidence_id="search:none", capability="web_search", source="web:fixture",
        observed_at=datetime.now(UTC), rows=[],
    )
    gaps = _empty_evidence_gaps([empty])
    assert len(gaps) == 1
    assert gaps[0].kind == "missing_evidence"
    assert gaps[0].evidence_ids == ["search:none"]
    assert gaps[0].message == "web_search returned no evidence values"


def test_runtime_result_rejects_adjudication_outside_draft() -> None:
    import pytest
    from pydantic import ValidationError
    from v2.contracts import DraftReport, Plan, TaskSpec
    from v2.runtime.models import ExecutionResult, RuntimeResult

    with pytest.raises(ValidationError, match="outside the draft"):
        RuntimeResult(
            task=TaskSpec(goal="answer", mode="quick", deliverable="text"),
            execution=ExecutionResult(plan=Plan(nodes=[])),
            draft=DraftReport(sections=["Answer"], claims=[]),
            verification=VerificationReport(status="pass", claim_results=[
                ClaimResult(claim_index=7, supported=True),
            ]),
        )


def test_runtime_result_rejects_gap_with_unknown_structured_block() -> None:
    import pytest
    from pydantic import ValidationError
    from v2.contracts import Gap, Plan, TaskSpec
    from v2.runtime.models import ExecutionResult, RuntimeResult

    base = dict(
        task=TaskSpec(goal="answer", mode="quick", deliverable="text"),
        execution=ExecutionResult(plan=Plan(nodes=[])),
        draft=DraftReport(sections=[], claims=[]),
        verification=VerificationReport(status="partial"),
    )
    for block in ("claim:0", "node:missing", "claim:bad"):
        with pytest.raises(ValidationError, match="gap blocks unknown"):
            RuntimeResult(**base, gaps=[Gap(
                kind="missing_evidence", message="missing", blocks=[block])])


def test_runtime_result_rejects_missing_verified_supported_claim() -> None:
    import pytest
    from pydantic import ValidationError
    from v2.contracts import Plan, TaskSpec
    from v2.runtime.models import ExecutionResult, RuntimeResult

    draft = DraftReport(sections=["Answer"], claims=[
        Claim(text="This is my judgment.", kind="judgment")])
    with pytest.raises(ValidationError, match="match supported adjudications"):
        RuntimeResult(
            task=TaskSpec(goal="answer", mode="quick", deliverable="text"),
            execution=ExecutionResult(plan=Plan(nodes=[])), draft=draft,
            verification=VerificationReport(status="pass", claim_results=[
                ClaimResult(claim_index=0, supported=True)]),
            verified_claims=[],
        )


def test_runtime_result_rejects_task_scoped_evidence_from_wrong_season() -> None:
    import pytest
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.contracts import EvidenceEnvelope, Plan, PlanNode, SeasonRef, TaskSpec
    from v2.runtime.models import ExecutionResult, RuntimeResult

    evidence = EvidenceEnvelope(
        evidence_id="old", capability="standings", source="fixture",
        observed_at=datetime.now(UTC), season="2024-25", rows={"wins": 61})
    execution = ExecutionResult(
        plan=Plan(nodes=[PlanNode(id="facts", description="facts",
            capability_hints=["standings"], status="complete")]),
        evidence_by_node={"facts": evidence}, attempts={"facts": 1})
    with pytest.raises(ValidationError, match="does not match task season"):
        RuntimeResult(
            task=TaskSpec(goal="record", mode="quick", deliverable="text",
                season=SeasonRef(value="2025-26", source="user", confidence=1)),
            execution=execution, draft=DraftReport(sections=[], claims=[]),
            verification=VerificationReport(status="partial"))


def test_runtime_result_rejects_pass_with_partial_publication_state() -> None:
    import pytest
    from pydantic import ValidationError
    from v2.contracts import Gap, Plan, TaskSpec
    from v2.runtime.models import ExecutionResult, RuntimeResult

    base = dict(
        task=TaskSpec(goal="answer", mode="quick", deliverable="text"),
        execution=ExecutionResult(plan=Plan(nodes=[])),
        draft=DraftReport(sections=["Answer"], claims=[]),
        verification=VerificationReport(status="pass"),
    )
    with pytest.raises(ValidationError, match="publication state"):
        RuntimeResult(**base, gaps=[Gap(kind="missing_evidence", message="missing")])


def test_runtime_result_rejects_partial_without_publication_gap() -> None:
    import pytest
    from pydantic import ValidationError
    from v2.contracts import Plan, TaskSpec
    from v2.runtime.models import ExecutionResult, RuntimeResult

    with pytest.raises(ValidationError, match="publication state"):
        RuntimeResult(
            task=TaskSpec(goal="answer", mode="quick", deliverable="text"),
            execution=ExecutionResult(plan=Plan(nodes=[])),
            draft=DraftReport(sections=["Answer"], claims=[]),
            verification=VerificationReport(status="partial"),
        )


def test_runtime_result_rejects_duplicate_typed_gaps() -> None:
    import pytest
    from pydantic import ValidationError
    from v2.contracts import Gap, Plan, TaskSpec
    from v2.runtime.models import ExecutionResult, RuntimeResult

    gap = Gap(kind="missing_evidence", message="missing")
    with pytest.raises(ValidationError, match="gaps must not contain duplicates"):
        RuntimeResult(
            task=TaskSpec(goal="answer", mode="quick", deliverable="text"),
            execution=ExecutionResult(plan=Plan(nodes=[])),
            draft=DraftReport(sections=["No answer"], claims=[]),
            verification=VerificationReport(status="partial"),
            gaps=[gap, gap],
        )


def test_unsupported_claim_gap_preserves_multiple_evidence_references() -> None:
    draft = DraftReport(sections=["Answer"], claims=[
        Claim(text="The comparison is conclusive.", kind="judgment",
              evidence_ids=["stats", "salary"]),
    ])
    report = VerificationReport(status="partial", claim_results=[
        ClaimResult(claim_index=0, supported=False, reasons=["sources conflict"]),
    ])

    gap = _verification_gaps(draft, report)[0]

    assert gap.kind == "unsupported_claim"
    assert gap.message == "sources conflict"
    assert gap.evidence_ids == ["stats", "salary"]
    assert gap.blocks == ["claim:0"]


def test_output_status_matrix_and_projection_use_only_admitted_bindings():
    from types import SimpleNamespace
    from v2.api.routes import _answer_text
    from v2.contracts import Gap
    from v2.contracts import (EvidenceOutputBinding, EvidenceRequirement, Gap,
                              VerifiedClaim)
    from v2.runtime.models import build_output_statuses
    binding = EvidenceOutputBinding(requirement_id="record", output_id="WINS",
        node_id="facts", evidence_id="ev", selector="rows.WINS",
        value={"kind":"integer","value":61},
        unit={"kind":"declared","value":"count"}, domain="standings")
    claim = Claim(text="Ignore this prose: Boston won 999.", kind="observed",
                  evidence_ids=["ev"], output_bindings=[binding])
    verified = VerifiedClaim(claim_index=0, claim=claim, evidence_ids=["ev"],
                             output_bindings=[binding])
    task = TaskSpec(goal="record", mode="quick", deliverable="answer",
        requirements=[EvidenceRequirement(id="record", description="record",
            capability_options=["standings"], requested_outputs=["WINS","LOSSES"])])
    statuses = build_output_statuses(task, [verified], [])
    assert [(x.output_id,x.status) for x in statuses] == [
        ("WINS","complete"),("LOSSES","missing")]
    result = SimpleNamespace(output_statuses=statuses, gaps=[], verified_claims=[],
        execution=SimpleNamespace(evidence=[]))
    assert _answer_text(result) == "WINS = 61 (count)\nLOSSES could not be verified (missing)."
    assert "999" not in _answer_text(result)


def test_projection_uses_canonical_gap_kind_not_untrusted_message():
    from types import SimpleNamespace
    from v2.api.routes import _answer_text
    from v2.contracts import Gap
    result = SimpleNamespace(output_statuses=[], gaps=[Gap(
        kind="execution_failure", message="SECRET internal adapter path")],
        verified_claims=[],
        execution=SimpleNamespace(evidence=[]))
    text = _answer_text(result)
    assert text == "Some requested data was unavailable."
    assert "SECRET" not in text


def test_ratings_task_publishes_one_clean_label_and_row_per_metric():
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from v2.adapters.capabilities import CAPABILITIES
    from v2.adapters.core import build_envelope
    from v2.api.routes import _answer_text, _public_evidence
    from v2.contracts import (
        Claim, EntityRef, EvidenceOutputBinding, EvidenceRequirement, SeasonRef,
        VerificationReport)
    from v2.runtime.models import build_output_statuses

    metrics = ["NET_RATING", "OFF_RATING", "DEF_RATING"]
    unit = CAPABILITIES["team_ratings"].units["NET_RATING"]
    subject = EntityRef(id="1", type="team", display_name="Capital City Stars")
    row = {"TEAM_ID": 1, "TEAM_NAME": subject.display_name,
           "NET_RATING": 9.6, "OFF_RATING": 119.8, "DEF_RATING": 110.2}
    envelope = build_envelope(
        CAPABILITIES["team_ratings"], {"season": "2025-26"},
        {"ok": True, "rows": [row],
         "meta": {"source": "warehouse", "season": "2025-26",
                  "warehouse_id": "frozen-eval", "warehouse_sha256": "a" * 64}},
        entities=[subject], observed_at=datetime.now(UTC))
    requirement = EvidenceRequirement(
        id="capital_city_stars_team_ratings_2025_26",
        description="ratings for one team",
        capability_options=["team_ratings"], requested_outputs=list(metrics))
    task = TaskSpec(
        goal="ratings for one team", mode="quick", deliverable="ratings",
        requested_outputs=list(metrics),
        season=SeasonRef(value="2025-26", source="user", confidence=1.0),
        entities=[subject], requirements=[requirement])
    node = PlanNode(
        id="ratings", description="ratings for one team",
        capability_hints=["team_ratings"],
        covers_requirement_ids=[requirement.id], status="complete")
    execution = ExecutionResult(
        plan=Plan(nodes=[node]), evidence_by_node={node.id: envelope},
        attempts={node.id: 1})
    bindings = [
        EvidenceOutputBinding(
            requirement_kind="evidence", requirement_id=requirement.id,
            output_id=metric, node_id=node.id, evidence_id=envelope.evidence_id,
            selector=f"rows[0].{metric}", row_selector="rows[0]",
            subject_entity_type="team", subject_entity_id=subject.id,
            subject_selector="rows[0].TEAM_ID",
            value={"kind": "float", "value": row[metric]},
            unit={"kind": "declared", "value": unit}, domain="team_ratings")
        for metric in metrics]
    claim = Claim(text="ratings", kind="observed",
                  evidence_ids=[envelope.evidence_id],
                  output_bindings=bindings)
    draft = DraftReport(sections=["ratings"], claims=[claim])
    report = VerificationReport(status="pass", claim_results=[
        ClaimResult(claim_index=0, supported=True)])
    claims, gaps = _verified_claims(
        task, execution, draft, report,
        {envelope.evidence_id: envelope})
    assert gaps == []
    statuses = build_output_statuses(task, claims, [])
    assert len(statuses) == 2 * len(metrics)
    result = SimpleNamespace(
        output_statuses=statuses, gaps=[], draft=draft, verified_claims=[],
        execution=SimpleNamespace(evidence=[envelope]))
    assert _answer_text(result).splitlines() == [
        "NET_RATING [team:1] = 9.6 (points_per_100_possessions)",
        "OFF_RATING [team:1] = 119.8 (points_per_100_possessions)",
        "DEF_RATING [team:1] = 110.2 (points_per_100_possessions)"]
    tables = _public_evidence(result)[0]
    assert [item["output_id"] for item in tables] == metrics
    assert [item["value"] for item in tables] == ["9.6", "119.8", "110.2"]


def test_four_typed_values_project_complete_without_fragments():
    from types import SimpleNamespace
    from v2.contracts import OutputFinalStatus, EvidenceOutputBinding
    from v2.api.routes import _answer_text
    from v2.contracts import Gap
    values = [("ZERO",{"kind":"integer","value":0}),
              ("FLAG",{"kind":"boolean","value":False}),
              ("RATE",{"kind":"float","value":1.5}),
              ("EXACT",{"kind":"decimal","value":"0.123456789123456789"})]
    statuses=[]
    for output,value in values:
        binding=EvidenceOutputBinding(requirement_kind="task",output_id=output,
            node_id="n",evidence_id="e",selector=f"rows.{output}",value=value,
            unit={"kind":"unitless"},domain="standings")
        statuses.append(OutputFinalStatus(requirement_kind="task",output_id=output,
            status="complete",claim_index=0,binding=binding))
    text=_answer_text(SimpleNamespace(output_statuses=statuses,gaps=[],verified_claims=[],
        execution=SimpleNamespace(evidence=[])))
    assert text.splitlines()==["ZERO = 0 (unitless)",
        "FLAG = false (unitless)", "RATE = 1.5 (unitless)",
        "EXACT = 0.123456789123456789 (unitless)"]


def test_probe_five_abstains_without_admitted_output_authority():
    from types import SimpleNamespace
    from v2.api.routes import _answer_text
    claims = [Claim(text=f"Unsupported prose {i}: 999", kind="judgment")
              for i in range(5)]
    task = TaskSpec(goal="probe", mode="quick", deliverable="answer",
                    requested_outputs=["DECISION"])
    statuses = __import__('v2.runtime.models',fromlist=['build_output_statuses']).build_output_statuses(
        task, [], [])
    assert statuses[0].status == "missing"
    assert _answer_text(SimpleNamespace(output_statuses=statuses,gaps=[],verified_claims=[],
        execution=SimpleNamespace(evidence=[]))) == (
        "DECISION could not be verified (missing).")


def test_mixed_branch_matrix_preserves_complete_and_missing():
    from v2.contracts import EvidenceOutputBinding, EvidenceRequirement, VerifiedClaim
    from v2.runtime.models import build_output_statuses
    binding = EvidenceOutputBinding(requirement_id="record",output_id="WINS",
        node_id="facts",evidence_id="ev",selector="rows.WINS",
        value={"kind":"integer","value":61},unit={"kind":"declared","value":"count"},
        domain="standings")
    claim=Claim(text="61",kind="observed",evidence_ids=["ev"],output_bindings=[binding])
    task=TaskSpec(goal="record",mode="quick",deliverable="answer",requirements=[
        EvidenceRequirement(id="record",description="record",capability_options=["standings"],requested_outputs=["WINS"]),
        EvidenceRequirement(id="pace",description="pace",capability_options=["team_ratings"],requested_outputs=["PACE"])])
    matrix=build_output_statuses(task,[VerifiedClaim(claim_index=0,claim=claim,evidence_ids=["ev"],output_bindings=[binding])],[])
    assert [(x.requirement_id,x.status) for x in matrix]==[("record","complete"),("pace","missing")]


def test_status_identity_must_match_binding_and_roundtrips():
    import json, pytest
    from v2.contracts import OutputFinalStatus, EvidenceOutputBinding
    binding=EvidenceOutputBinding(requirement_kind="task",output_id="WINS",
        node_id="n",evidence_id="e",selector="rows.WINS",
        value={"kind":"integer","value":61},unit={"kind":"declared","value":"count"},
        domain="standings")
    status=OutputFinalStatus(requirement_kind="task",output_id="WINS",status="complete",
                             claim_index=0,binding=binding)
    assert OutputFinalStatus.model_validate_json(status.model_dump_json())==status
    payload=status.model_dump(mode="json");payload["output_id"]="LOSSES"
    with pytest.raises(Exception):OutputFinalStatus.model_validate_json(json.dumps(payload))


def test_two_subjects_same_output_and_unit_are_self_contained():
    from types import SimpleNamespace
    from v2.api.routes import _answer_text
    from v2.contracts import OutputFinalStatus, EvidenceOutputBinding
    statuses=[]
    for req,subject,value in [("lebron","23",25),("curry","30",30)]:
        binding=EvidenceOutputBinding(requirement_id=req,output_id="PTS",node_id=req,
            evidence_id=req,selector=f"rows.{req}.PTS",row_selector=f"rows.{req}",
            subject_entity_type="player",subject_entity_id=subject,
            subject_selector=f"rows.{req}.PLAYER_ID",value={"kind":"integer","value":value},
            unit={"kind":"declared","value":"points"},domain="player_report")
        statuses.append(OutputFinalStatus(requirement_kind="evidence",requirement_id=req,
            output_id="PTS",status="complete",claim_index=0,binding=binding))
    assert _answer_text(SimpleNamespace(output_statuses=statuses,gaps=[],verified_claims=[],
        execution=SimpleNamespace(evidence=[]))).splitlines()==[
        "PTS [player:23] = 25 (points)",
        "PTS [player:30] = 30 (points)"]


def test_calculation_projection_and_input_evidence_filtering():
    from decimal import Decimal
    from types import SimpleNamespace
    from v2.api.routes import _answer_text, _public_evidence
    from v2.contracts import (OutputFinalStatus, CalculationOutputBinding,
        DraftReport, DeclaredCalculation, DeclaredCalculationInput)
    binding=CalculationOutputBinding(requirement_id="delta",output_id="PTS_DELTA",
                                     calculation_id="calc")
    status=OutputFinalStatus(requirement_kind="calculation",requirement_id="delta",
        output_id="PTS_DELTA",status="complete",claim_index=0,binding=binding)
    calc=DeclaredCalculation(calculation_id="calc",requirement_id="delta",
        operation="subtract",inputs=[DeclaredCalculationInput(evidence_id="a",path="rows.PTS"),
        DeclaredCalculationInput(evidence_id="b",path="rows.PTS")],result=Decimal("-5"),unit="points")
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope
    result=SimpleNamespace(output_statuses=[status],gaps=[],draft=DraftReport(
        sections=[],claims=[],calculations=[calc]),verified_claims=[],
        execution=SimpleNamespace(evidence=[
        EvidenceEnvelope(evidence_id="a",capability="player_report",source="a",observed_at=datetime.now(UTC),rows={"PTS":25}),
        EvidenceEnvelope(evidence_id="b",capability="player_report",source="b",observed_at=datetime.now(UTC),rows={"PTS":30})]))
    assert _answer_text(result)=="PTS_DELTA = -5 (points)"
    assert len(_public_evidence(result)[0]) == 2


def test_public_evidence_projection_excludes_sibling_rows_and_metrics():
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from v2.api.routes import _public_evidence
    from v2.contracts import EvidenceEnvelope, EvidenceOutputBinding, OutputFinalStatus
    binding=EvidenceOutputBinding(requirement_kind="task",output_id="PTS",node_id="n",
        evidence_id="ev",selector="rows.lebron.PTS",row_selector="rows.lebron",
        subject_entity_type="player",subject_entity_id="23",
        subject_selector="rows.lebron.PLAYER_ID",value={"kind":"integer","value":25},
        unit={"kind":"declared","value":"points"},domain="player_report")
    status=OutputFinalStatus(requirement_kind="task",output_id="PTS",status="complete",
                             claim_index=0,binding=binding)
    envelope=EvidenceEnvelope(evidence_id="ev",capability="player_report",source="fixture",
        observed_at=datetime.now(UTC),rows={"lebron":{"PLAYER_ID":"23","PTS":25,"AST":8},
        "curry":{"PLAYER_ID":"30","PTS":30}})
    result=SimpleNamespace(output_statuses=[status],draft=DraftReport(sections=[],claims=[]),
        execution=ExecutionResult(plan=Plan(nodes=[PlanNode(id="n",description="n",
        capability_hints=["player_report"],status="complete")]),evidence_by_node={"n":envelope},attempts={"n":1}))
    encoded=str(_public_evidence(result)[0])
    assert "25" in encoded and "30" not in encoded and "AST" not in encoded and "curry" not in encoded


def test_public_projection_rejects_stale_evidence_and_missing_calculation_input():
    import pytest
    from copy import deepcopy
    from v2.api.routes import _public_evidence
    from types import SimpleNamespace
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope, EvidenceOutputBinding, OutputFinalStatus
    binding=EvidenceOutputBinding(requirement_kind="task",output_id="WINS",node_id="n",
        evidence_id="e",selector="rows.WINS",value={"kind":"integer","value":61},
        unit={"kind":"declared","value":"count"},domain="standings")
    status=OutputFinalStatus(requirement_kind="task",output_id="WINS",status="complete",
                             claim_index=0,binding=binding)
    stale=EvidenceEnvelope(evidence_id="e",capability="standings",source="SECRET",
        observed_at=datetime.now(UTC),rows={"WINS":62})
    result=SimpleNamespace(output_statuses=[status],draft=DraftReport(sections=[],claims=[]),
                           execution=SimpleNamespace(evidence=[stale]))
    with pytest.raises(ValueError,match="changed"):_public_evidence(result)


def test_calculation_projection_rejects_missing_and_ambiguous_inputs():
    import pytest
    from decimal import Decimal
    from types import SimpleNamespace
    from datetime import UTC, datetime
    from v2.api.routes import _public_evidence
    from v2.contracts import (OutputFinalStatus, CalculationOutputBinding,
        DeclaredCalculation, DeclaredCalculationInput, EvidenceEnvelope)
    binding=CalculationOutputBinding(requirement_id="d",output_id="DELTA",calculation_id="c")
    status=OutputFinalStatus(requirement_kind="calculation",requirement_id="d",
        output_id="DELTA",status="complete",claim_index=0,binding=binding)
    calc=DeclaredCalculation(calculation_id="c",requirement_id="d",operation="subtract",
        inputs=[DeclaredCalculationInput(evidence_id="a",path="rows[].PTS"),
                DeclaredCalculationInput(evidence_id="b",path="rows.PTS")],result=Decimal("-5"))
    a=EvidenceEnvelope(evidence_id="a",capability="player_report",source="a",
        observed_at=datetime.now(UTC),rows=[{"PTS":25},{"PTS":26}])
    b=EvidenceEnvelope(evidence_id="b",capability="player_report",source="b",
        observed_at=datetime.now(UTC),rows={"PTS":30})
    result=SimpleNamespace(output_statuses=[status],draft=DraftReport(sections=[],claims=[],calculations=[calc]),
                           execution=SimpleNamespace(evidence=[a,b]))
    with pytest.raises(ValueError):_public_evidence(result)
    missing_calc=calc.model_copy(update={"inputs":[
        DeclaredCalculationInput(evidence_id="missing",path="rows.PTS"),
        DeclaredCalculationInput(evidence_id="b",path="rows.PTS")]})
    missing_result=SimpleNamespace(output_statuses=[status],
        draft=DraftReport(sections=[],claims=[],calculations=[missing_calc]),
        execution=SimpleNamespace(evidence=[b]))
    with pytest.raises((ValueError,KeyError)):_public_evidence(missing_result)


def test_buffered_event_projection_drops_secrets_and_internal_ids():
    from types import SimpleNamespace
    from v2.api.routes import _safe_buffered_event
    secret=SimpleNamespace(type="thought_stream",text="SECRET",status="running",
                           phase="verify",event_id="internal-1")
    safe=_safe_buffered_event(secret)
    encoded=safe.model_dump_json()
    assert "SECRET" not in encoded and "internal-1" not in encoded
    assert '"node":"analytics"' in encoded


def test_public_event_contract_closes_nodes_tools_and_work_log():
    from types import SimpleNamespace
    from v2.api.routes import _safe_buffered_event
    from v2.api.events import WorkLog
    from v2.api.sse import encode_event
    assert _safe_buffered_event(SimpleNamespace(type="node_update",node="SECRET",status="running")) is None
    safe=_safe_buffered_event(SimpleNamespace(type="tool_result",status="ok",rows="SECRET",ms="SECRET"))
    encoded=encode_event(safe)
    assert "SECRET" not in encoded and "rows" not in encoded and "ms" not in encoded
    work=encode_event(WorkLog(run_id="run-"+"a"*32,status="complete"))
    assert '"run_id":"run-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"' in work


def _seed_completed_season_boxscores(monkeypatch, tmp_path):
    import duckdb

    from shared import store

    warehouse = tmp_path / "warehouse.duckdb"
    connection = duckdb.connect(str(warehouse))
    connection.execute(
        "CREATE TABLE silver_leaders_ast (RANK BIGINT, PLAYER VARCHAR, "
        "TEAM VARCHAR, GP BIGINT, AST BIGINT, MIN BIGINT, _source VARCHAR, "
        "_season VARCHAR, _fetched_at VARCHAR)"
    )
    connection.execute(
        "INSERT INTO silver_leaders_ast VALUES (1, 'Current Star', 'DEN', "
        "65, 697, 2200, 'nba_stats', '2025-26', "
        "'2026-09-30T00:00:00+00:00')"
    )
    connection.execute(
        "CREATE TABLE silver_boxscores (PLAYER_ID BIGINT, firstName VARCHAR, "
        "familyName VARCHAR, GAME_ID VARCHAR, teamTricode VARCHAR, "
        "assists BIGINT, comment VARCHAR, _source VARCHAR, _season VARCHAR, "
        "_fetched_at VARCHAR, _entity VARCHAR)"
    )
    rows = []
    game = 2000
    for _ in range(60):
        game += 1
        rows.append(
            f"(1629027, 'Trae', 'Young', 'G{game}', 'ATL', 12, '', "
            "'nba_stats', '2024-25', '2025-06-01T00:00:00+00:00', '')"
        )
    for _ in range(16):
        game += 1
        rows.append(
            f"(1629027, 'Trae', 'Young', 'G{game}', 'ATL', 10, '', "
            "'nba_stats', '2024-25', '2025-06-01T00:00:00+00:00', '')"
        )
    rows.append(
        "(1629027, 'Trae', 'Young', 'G9999', 'ATL', 0, "
        "'DND - Injury/Illness', 'nba_stats', '2024-25', "
        "'2025-06-01T00:00:00+00:00', '')"
    )
    for _ in range(70):
        game += 1
        rows.append(
            f"(1630162, 'Second', 'Guard', 'G{game}', 'DET', 10, '', "
            "'nba_stats', '2024-25', '2025-06-01T00:00:00+00:00', '')"
        )
    connection.execute("INSERT INTO silver_boxscores VALUES " + ",".join(rows))
    connection.close()
    monkeypatch.setattr(store, "DB_PATH", warehouse)
    return warehouse


def test_completed_season_assists_leader_publishes_count(monkeypatch, tmp_path):
    import asyncio
    from types import SimpleNamespace

    from v2.adapters.core import ToolCapability
    from v2.api.routes import _answer_text
    from v2.contracts import (
        Claim,
        ClaimKind,
        DraftReport,
        EvidenceOutputBinding,
        EvidenceRequirement,
        SeasonRef,
        VerifiedClaim,
    )
    from v2.runtime.executor import PlanExecutor
    from v2.runtime.loop import _verified_claims
    from v2.runtime.models import admit_verified_claim_bindings, build_output_statuses
    from v2.runtime.verifier import verify_mechanical

    _seed_completed_season_boxscores(monkeypatch, tmp_path)
    task = TaskSpec(
        goal="Who led the NBA in assists in the 2024-25 season, and how many?",
        mode="quick", deliverable="Assists leader and total assists",
        requested_outputs=["AST"],
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        requirements=[EvidenceRequirement(
            id="assists_leader_2024_25",
            description="2024-25 NBA assists leaderboard",
            capability_options=["qualified_leaders"],
            capability_arguments={"stat_category": "AST", "season": "2024-25"},
            requested_outputs=["AST"])])
    plan = Plan(nodes=[PlanNode(
        id="leader", description="Fetch 2024-25 assists leaderboard",
        capability_hints=["qualified_leaders"],
        covers_requirement_ids=["assists_leader_2024_25"],
        arguments={"stat_category": "AST", "season": "2024-25"})])
    execution = asyncio.run(PlanExecutor(
        {"qualified_leaders": ToolCapability("qualified_leaders")}
    ).execute(task, plan))
    envelope = execution.evidence[0]
    binding = EvidenceOutputBinding(
        requirement_kind="evidence", requirement_id="assists_leader_2024_25",
        output_id="AST", node_id="leader", evidence_id=envelope.evidence_id,
        selector="rows[0].AST", value={"kind": "integer", "value": 880},
        unit={"kind": "declared", "value": "count"},
        domain="qualified_leaders")
    claim = Claim(
        text="Trae Young led the NBA with 880 assists in 2024-25.",
        kind=ClaimKind.OBSERVED, evidence_ids=[envelope.evidence_id],
        output_bindings=[binding])
    draft = DraftReport(sections=["Assists leader"], claims=[claim], gaps=[])
    verification = verify_mechanical(task, draft, execution.evidence)
    assert verification.claim_results[0].supported
    candidate = VerifiedClaim(
        claim_index=0, claim=claim, evidence_ids=[envelope.evidence_id],
        sources=[], output_bindings=[binding])
    candidate = candidate.model_copy(update={
        "sources": [
            {"evidence_id": envelope.evidence_id, "source": envelope.source,
             "capability": envelope.capability,
             "observed_at": envelope.observed_at, "as_of": envelope.as_of,
             "vintages": dict(envelope.vintages)}]})
    admit_verified_claim_bindings(task, execution, draft, candidate)
    claims, gaps = _verified_claims(
        task, execution, draft, verification,
        {item.evidence_id: item for item in execution.evidence})
    assert gaps == []
    statuses = build_output_statuses(task, claims, [])
    assert ("evidence", "assists_leader_2024_25", "AST") in [
        (item.requirement_kind, item.requirement_id, item.output_id)
        for item in statuses if item.status == "complete"]
    text = _answer_text(SimpleNamespace(
        output_statuses=statuses, gaps=[], draft=draft,
        execution=execution, verification=verification,
        verified_claims=claims))
    assert text.splitlines()[0] == "Trae Young led the NBA with 880 assists in 2024-25."
    assert "AST = 880 (count)" not in text


def _display_table(output_id, definitions=None, rows=None):
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from v2.api.routes import _public_evidence
    from v2.contracts import EvidenceEnvelope, EvidenceOutputBinding, OutputFinalStatus
    binding = EvidenceOutputBinding(requirement_kind="task", output_id=output_id,
        node_id="n", evidence_id="ev", selector=f"rows.{output_id}",
        value={"kind": "integer", "value": 25},
        unit={"kind": "declared", "value": "points"}, domain="player_report")
    status = OutputFinalStatus(requirement_kind="task", output_id=output_id,
        status="complete", claim_index=0, binding=binding)
    envelope = EvidenceEnvelope(evidence_id="ev", capability="player_report",
        source="fixture", observed_at=datetime.now(UTC),
        metric_definitions=definitions or {},
        rows=rows or {output_id: 25})
    result = SimpleNamespace(output_statuses=[status],
        draft=DraftReport(sections=[], claims=[]),
        execution=SimpleNamespace(evidence=[envelope]))
    return _public_evidence(result)[0][0]


def test_public_table_display_name_prefers_metric_definition_head():
    table = _display_table("EFG_PCT", definitions={
        "EFG_PCT": "Effective field-goal percentage: (FGM + 0.5 * FG3M) / FGA."},
        rows={"EFG_PCT": 25})
    assert table["output_id"] == "EFG_PCT"
    assert table["display_name"] == "Effective field-goal percentage"


def test_public_table_display_name_humanizes_bare_output_id():
    from v2.api.routes import _output_display_name
    assert _display_table("PPG")["display_name"] == "PPG"
    assert _display_table("PTS_DELTA")["display_name"] == "PTS DELTA"
    assert _output_display_name("ppg") == "PPG"


def test_public_output_status_carries_display_name():
    from types import SimpleNamespace
    from v2.api.routes import _public_output_status
    from v2.contracts import EvidenceOutputBinding, OutputFinalStatus
    binding = EvidenceOutputBinding(requirement_kind="task", output_id="PTS",
        node_id="n", evidence_id="e", selector="rows.PTS",
        value={"kind": "integer", "value": 25},
        unit={"kind": "declared", "value": "points"}, domain="standings")
    status = OutputFinalStatus(requirement_kind="task", output_id="PTS",
        status="complete", claim_index=0, binding=binding)
    assert _public_output_status(SimpleNamespace(), status)["display_name"] == "PTS"


def _subject_table(subject_id, entities):
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from v2.api.routes import _public_evidence
    from v2.contracts import (DraftReport, EvidenceEnvelope,
                              EvidenceOutputBinding, OutputFinalStatus)
    binding = EvidenceOutputBinding(
        requirement_kind="task", output_id="PTS", node_id="n",
        evidence_id="ev", selector="rows.r.PTS", row_selector="rows.r",
        subject_entity_type="player", subject_entity_id=subject_id,
        subject_selector="rows.r.PLAYER_ID",
        value={"kind": "integer", "value": 25},
        unit={"kind": "declared", "value": "points"}, domain="player_report")
    status = OutputFinalStatus(requirement_kind="task", output_id="PTS",
        status="complete", claim_index=0, binding=binding)
    envelope = EvidenceEnvelope(evidence_id="ev", capability="player_report",
        source="fixture", observed_at=datetime.now(UTC), entities=entities,
        rows={"r": {"PLAYER_ID": subject_id, "PTS": 25}})
    result = SimpleNamespace(output_statuses=[status],
        draft=DraftReport(sections=[], claims=[]),
        execution=SimpleNamespace(evidence=[envelope]))
    return _public_evidence(result)[0]


def test_public_table_subject_display_name_resolves_numeric_player_id():
    table = _subject_table("1629027", [{"id": "1629027", "type": "player",
                                        "display_name": "Trae Young"}])[0]
    assert table["subject_id"] == "1629027"
    assert table["subject_display_name"] == "Trae Young"


def test_public_table_subject_display_name_empty_for_unknown_id():
    table = _subject_table("9999999", [{"id": "1629027", "type": "player",
                                        "display_name": "Trae Young"}])[0]
    assert table["subject_display_name"] == ""


def test_public_output_status_carries_subject_display_name():
    from types import SimpleNamespace
    from v2.api.routes import _public_output_status
    from v2.contracts import EvidenceOutputBinding, OutputFinalStatus
    binding = EvidenceOutputBinding(
        requirement_kind="task", output_id="PTS", node_id="n",
        evidence_id="e", selector="rows.r.PTS", row_selector="rows.r",
        subject_entity_type="player", subject_entity_id="1629027",
        subject_selector="rows.r.PLAYER_ID",
        value={"kind": "integer", "value": 25},
        unit={"kind": "declared", "value": "points"}, domain="player_report")
    status = OutputFinalStatus(requirement_kind="task", output_id="PTS",
        status="complete", claim_index=0, binding=binding)
    assert _public_output_status(SimpleNamespace(), status)["subject_display_name"] == ""


def test_public_gaps_plumb_blocks():
    from types import SimpleNamespace
    from v2.api.routes import _public_gaps
    from v2.contracts import Gap, GapKind
    result = SimpleNamespace(gaps=[
        Gap(kind=GapKind.MISSING_EVIDENCE, message="no data",
            blocks=["requirement:assists", "claim:1"]),
        Gap(kind=GapKind.SOURCE_CONFLICT, message="conflict", blocks=[]),
    ])
    assert _public_gaps(result) == [
        {"kind": "missing_evidence", "blocks": ["requirement:assists", "claim:1"]},
        {"kind": "source_conflict", "blocks": []},
    ]

