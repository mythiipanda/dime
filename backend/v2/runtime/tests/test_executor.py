from __future__ import annotations

import asyncio

import pytest
from v2.contracts import Plan, PlanNode, PlanStatus, RunMode, TaskSpec


def node(
    node_id: str, *, parents: list[str] | None = None, attempts: int = 1
) -> PlanNode:
    return PlanNode(
        id=node_id,
        description=node_id,
        depends_on=parents or [],
        capability_hints=["fake"],
        max_attempts=attempts,
    )


def test_execution_result_rejects_unknown_state_nodes_and_duplicate_evidence() -> None:
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.models import ExecutionResult

    plan = Plan(nodes=[node("known")])
    with pytest.raises(ValidationError, match="unknown nodes"):
        ExecutionResult(plan=plan, attempts={"invented": 1})
    evidence = EvidenceEnvelope(
        evidence_id="same", capability="fake", source="fixture",
        observed_at=datetime.now(UTC), rows={},
    )
    with pytest.raises(ValidationError, match="evidence ids must be unique"):
        ExecutionResult(plan=Plan(nodes=[node("a"), node("b")]), evidence_by_node={"a": evidence, "b": evidence})

def test_execution_result_requires_one_evidence_per_completed_node() -> None:
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.models import ExecutionResult

    completed = node("done").model_copy(update={"status": PlanStatus.COMPLETE})
    ExecutionResult(plan=Plan(nodes=[completed]), attempts={"done": 1})
    pending = node("pending")
    evidence = EvidenceEnvelope(
        evidence_id="ev", capability="fake", source="fixture",
        observed_at=datetime.now(UTC), rows={},
    )
    with pytest.raises(ValidationError, match="owner must be complete"):
        ExecutionResult(plan=Plan(nodes=[pending]), evidence_by_node={"pending": evidence})
    with pytest.raises(ValidationError, match="non-negative"):
        ExecutionResult(plan=Plan(nodes=[pending]), attempts={"pending": -1})

def test_execution_result_binds_evidence_capability_and_lineage_to_plan() -> None:
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.models import ExecutionResult

    parent = node("parent").model_copy(update={"status": PlanStatus.COMPLETE})
    child = node("child", parents=["parent"]).model_copy(
        update={"status": PlanStatus.COMPLETE})
    parent_evidence = EvidenceEnvelope(
        evidence_id="parent-ev", capability="fake", source="fixture",
        observed_at=datetime.now(UTC), rows={},
    )
    child_evidence = EvidenceEnvelope(
        evidence_id="child-ev", capability="fake", source="fixture",
        observed_at=datetime.now(UTC), rows={}, lineage=[],
    )
    with pytest.raises(ValidationError, match="lineage does not match"):
        ExecutionResult(
            plan=Plan(nodes=[parent, child]),
            evidence_by_node={"parent": parent_evidence, "child": child_evidence},
            attempts={"parent": 1, "child": 1},
        )
    wrong_capability = parent_evidence.model_copy(update={"capability": "other"})
    with pytest.raises(ValidationError, match="capability does not match"):
        ExecutionResult(plan=Plan(nodes=[parent]), evidence_by_node={"parent": wrong_capability}, attempts={"parent": 1})


def test_execution_result_binds_attempts_and_errors_to_node_state() -> None:
    from pydantic import ValidationError
    from v2.runtime.models import ExecutionResult

    pending = node("pending")
    with pytest.raises(ValidationError, match="exceed max_attempts"):
        ExecutionResult(plan=Plan(nodes=[pending]), attempts={"pending": 2})
    failed = pending.model_copy(update={"status": PlanStatus.FAILED})
    with pytest.raises(ValidationError, match="requires errors"):
        ExecutionResult(plan=Plan(nodes=[failed]), attempts={"pending": 1})
    skipped = pending.model_copy(update={"status": PlanStatus.SKIPPED})
    with pytest.raises(ValidationError, match="cannot carry errors"):
        ExecutionResult(
            plan=Plan(nodes=[skipped]), errors={"pending": ["contradiction"]},
        )

def test_execution_result_rejects_unattempted_completed_or_failed_node() -> None:
    from datetime import UTC, datetime
    from pydantic import ValidationError
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.models import ExecutionResult

    completed = node("done").model_copy(update={"status": PlanStatus.COMPLETE})
    evidence = EvidenceEnvelope(
        evidence_id="done", capability="fake", source="fixture",
        observed_at=datetime.now(UTC), rows={"value": 1},
    )
    with pytest.raises(ValidationError, match="without an attempt"):
        ExecutionResult(plan=Plan(nodes=[completed]), evidence_by_node={"done": evidence})
    failed = node("failed").model_copy(update={"status": PlanStatus.FAILED})
    with pytest.raises(ValidationError, match="without an attempt"):
        ExecutionResult(
            plan=Plan(nodes=[failed]), errors={"failed": ["failure"]},
        )

@pytest.mark.parametrize("errors,message", [([" "], "empty errors"), (["same", "same"], "duplicate errors")])
def test_execution_result_rejects_invalid_error_messages(errors, message) -> None:
    from pydantic import ValidationError
    from v2.runtime.models import ExecutionResult

    failed = node("failed").model_copy(update={"status": PlanStatus.FAILED})
    with pytest.raises(ValidationError, match=message):
        ExecutionResult(
            plan=Plan(nodes=[failed]), attempts={"failed": 1},
            errors={"failed": errors},
        )

def test_execution_result_rejects_nonterminal_node_without_attempts_remaining() -> None:
    from pydantic import ValidationError
    from v2.runtime.models import ExecutionResult

    pending = node("pending", attempts=1)
    with pytest.raises(ValidationError, match="no attempts remaining"):
        ExecutionResult(plan=Plan(nodes=[pending]), attempts={"pending": 1})


def test_execution_result_rejects_failed_node_with_attempts_remaining() -> None:
    from pydantic import ValidationError
    from v2.runtime.models import ExecutionResult

    failed = node("failed", attempts=2).model_copy(update={"status": PlanStatus.FAILED})
    with pytest.raises(ValidationError, match="exhaust its attempt budget"):
        ExecutionResult(
            plan=Plan(nodes=[failed]), attempts={"failed": 1},
            errors={"failed": ["failure"]},
        )

def test_execution_result_rejects_skipped_node_with_attempts() -> None:
    from pydantic import ValidationError
    from v2.runtime.models import ExecutionResult

    skipped = node("skipped").model_copy(update={"status": PlanStatus.SKIPPED})
    with pytest.raises(ValidationError, match="cannot carry attempts"):
        ExecutionResult(plan=Plan(nodes=[skipped]), attempts={"skipped": 1})

@pytest.mark.parametrize("count", [True, 1.5, "1"])
def test_execution_result_rejects_noninteger_attempt_counts(count) -> None:
    from pydantic import ValidationError
    from v2.runtime.models import ExecutionResult
    with pytest.raises(ValidationError, match="valid integer|attempt counts must be integers"):
        ExecutionResult(plan=Plan(nodes=[node("pending")]), attempts={"pending": count})


def test_execution_result_bounds_errors_per_node() -> None:
    from pydantic import ValidationError
    from v2.runtime.models import ExecutionResult
    failed = node("failed", attempts=5).model_copy(update={"status": PlanStatus.FAILED})
    with pytest.raises(ValidationError, match="too many errors"):
        ExecutionResult(plan=Plan(nodes=[failed]), attempts={"failed": 5},
                        errors={"failed": [f"error-{index}" for index in range(6)]})


def _owned_execution(*, reordered=False, control=False):
    from datetime import UTC,datetime
    from v2.contracts import EvidenceEnvelope,Plan,PlanNode
    from v2.runtime.models import ExecutionResult
    ev1=EvidenceEnvelope(evidence_id="one",capability="standings",source="fixture",observed_at=datetime.now(UTC),rows={"WINS":0,"ACTIVE":False,"LOSSES":7})
    ev2=EvidenceEnvelope(evidence_id="two",capability="standings",source="fixture",observed_at=datetime.now(UTC),rows={"LOSSES":7})
    nodes=[PlanNode(id="n1",description="one",capability_hints=["standings"],covers_requirement_ids=["a"],status="complete"),PlanNode(id="n2",description="two",capability_hints=["standings"],covers_requirement_ids=["b"],status="complete")]
    if control:nodes.insert(1,PlanNode(id="resolve",description="control",capability_hints=[],status="complete"))
    owned={"n2":ev2,"n1":ev1} if reordered else {"n1":ev1,"n2":ev2}
    attempts={n.id:1 for n in nodes}
    return ExecutionResult(plan=Plan(nodes=nodes),evidence_by_node=owned,attempts=attempts)

def test_execution_ownership_is_explicit_under_reorder_and_control_node():
    execution=_owned_execution(reordered=True,control=True)
    assert execution.evidence_by_node["n1"].evidence_id=="one"
    assert "resolve" not in execution.evidence_by_node

def test_execution_rejects_orphan_wrong_node_and_duplicate_evidence():
    from pydantic import ValidationError
    good=_owned_execution()
    payload=good.model_dump();payload["evidence_by_node"]["orphan"]=payload["evidence_by_node"].pop("n1")
    with pytest.raises(ValidationError):type(good).model_validate(payload)
    payload=good.model_dump();payload["evidence_by_node"]["n2"]=payload["evidence_by_node"]["n1"]
    with pytest.raises(ValidationError):type(good).model_validate(payload)

def test_evidence_binding_preserves_zero_false_and_rejects_wrong_authority():
    from v2.contracts import TaskSpec,EvidenceRequirement,DraftReport,Claim,VerifiedClaim,EvidenceOutputBinding
    from v2.runtime.models import admit_verified_claim_bindings
    task=TaskSpec(goal="stats",mode="quick",deliverable="answer",requirements=[EvidenceRequirement(id="a",description="a",capability_options=["standings"],requested_outputs=["WINS","ACTIVE"]),EvidenceRequirement(id="b",description="b",capability_options=["standings"],requested_outputs=["LOSSES"])])
    execution=_owned_execution()
    for output,selector in [("WINS","rows.WINS"),("ACTIVE","rows.ACTIVE")]:
        binding=EvidenceOutputBinding(value=({"kind":"boolean","value":False} if output=="ACTIVE" else {"kind":"integer","value":0}), unit=({"kind":"unitless"} if output=="ACTIVE" else {"kind":"declared","value":"count"}), domain="standings", requirement_id="a",output_id=output,node_id="n1",evidence_id="one",selector=selector)
        claim=Claim(text="zero and inactive",kind="observed",evidence_ids=["one"],output_bindings=[binding]);draft=DraftReport(sections=[],claims=[claim])
        verified=VerifiedClaim(claim_index=0,claim=claim,evidence_ids=["one"],output_bindings=[binding])
        assert admit_verified_claim_bindings(task,execution,draft,verified) is verified
    bad=[dict(requirement_id="b",output_id="LOSSES",node_id="n1",evidence_id="one",selector="rows.WINS"),dict(requirement_id="a",output_id="LOSSES",node_id="n1",evidence_id="one",selector="rows.WINS"),dict(requirement_id="a",output_id="WINS",node_id="n1",evidence_id="one",selector="rows.NOPE")]
    for item in bad:
        binding=EvidenceOutputBinding(value={"kind":"integer","value":0}, unit={"kind":"unitless"}, domain="standings", **item)
        bad_claim=Claim(text="bad",kind="observed",evidence_ids=["one"],output_bindings=[binding])
        verified=VerifiedClaim(claim_index=0,claim=bad_claim,evidence_ids=["one"],output_bindings=[binding])
        with pytest.raises(ValueError):admit_verified_claim_bindings(task,execution,draft,verified)

def test_binding_rejects_existing_wrong_metric_and_wrong_capability():
    from v2.contracts import (TaskSpec, EvidenceRequirement, DraftReport, Claim,
                              VerifiedClaim, EvidenceOutputBinding)
    from v2.runtime.models import admit_verified_claim_bindings
    task = TaskSpec(goal="wins", mode="quick", deliverable="answer",
        requirements=[EvidenceRequirement(id="a", description="wins",
            capability_options=["standings"], requested_outputs=["WINS"])])
    execution = _owned_execution()
    for updates in [
        {"selector": "rows.LOSSES"},
        {"domain": "player_report"},
        {"unit": {"kind":"declared","value":"percent_0_100"}},
    ]:
        values = dict(requirement_id="a", output_id="WINS", node_id="n1",
                      evidence_id="one", selector="rows.WINS",
                      value={"kind":"integer","value":0},
                      unit={"kind":"declared","value":"count"},
                      domain="standings")
        values.update(updates)
        binding = EvidenceOutputBinding(**values)
        claim = Claim(text="wins", kind="observed", evidence_ids=["one"],
                      output_bindings=[binding])
        verified = VerifiedClaim(claim_index=0, claim=claim,
            evidence_ids=["one"], output_bindings=[binding])
        with pytest.raises(ValueError):
            admit_verified_claim_bindings(task, execution,
                DraftReport(sections=[], claims=[claim]), verified)
    wrong_task = task.model_copy(deep=True)
    wrong_task.requirements[0].capability_options = ["player_report"]
    binding = EvidenceOutputBinding(value={"kind":"integer","value":0}, unit={"kind":"declared","value":"count"}, domain="standings", requirement_id="a", output_id="WINS",
        node_id="n1", evidence_id="one", selector="rows.WINS")
    claim = Claim(text="wins", kind="observed", evidence_ids=["one"],
                  output_bindings=[binding])
    with pytest.raises(ValueError, match="capability"):
        admit_verified_claim_bindings(wrong_task, execution,
            DraftReport(sections=[], claims=[claim]),
            VerifiedClaim(claim_index=0, claim=claim,
                evidence_ids=["one"], output_bindings=[binding]))

def test_task_output_binding_and_selector_local_subject():
    from datetime import UTC, datetime
    from v2.contracts import (TaskSpec, DraftReport, Claim, VerifiedClaim,
        EvidenceOutputBinding, EntityRef, EvidenceEnvelope, Plan, PlanNode)
    from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings
    players = [EntityRef(id="23", type="player", display_name="LeBron"),
               EntityRef(id="30", type="player", display_name="Curry")]
    evidence = EvidenceEnvelope(evidence_id="pair", capability="player_report",
        source="fixture", observed_at=datetime.now(UTC), entities=players,
        rows=[{"PLAYER_ID":"23","PTS":25}, {"PLAYER_ID":"30","PTS":30}])
    execution = ExecutionResult(plan=Plan(nodes=[PlanNode(id="pair",
        description="pair", capability_hints=["player_report"], status="complete")]),
        evidence_by_node={"pair": evidence}, attempts={"pair": 1})
    task = TaskSpec(goal="LeBron points", mode="quick", deliverable="answer",
                    requested_outputs=["PTS"], entities=[players[0]])
    good = EvidenceOutputBinding(value={"kind":"integer","value":25}, unit={"kind":"unitless"}, domain="player_report", requirement_kind="task", output_id="PTS",
        node_id="pair", evidence_id="pair", selector="rows[0].PTS",
        subject_entity_type="player", subject_entity_id="23", subject_selector="rows[0].PLAYER_ID", row_selector="rows[0]")
    claim = Claim(text="LeBron scored 25", kind="observed",
                  evidence_ids=["pair"], output_bindings=[good])
    assert admit_verified_claim_bindings(task, execution,
        DraftReport(sections=[], claims=[claim]), VerifiedClaim(claim_index=0,
            claim=claim, evidence_ids=["pair"], output_bindings=[good]))
    wrong = good.model_copy(update={"selector":"rows[1].PTS"})
    wrong_claim = claim.model_copy(update={"output_bindings":[wrong]})
    with pytest.raises(ValueError, match="outside declared row"):
        admit_verified_claim_bindings(task, execution,
            DraftReport(sections=[], claims=[wrong_claim]),
            VerifiedClaim(claim_index=0, claim=wrong_claim,
                evidence_ids=["pair"], output_bindings=[wrong]))

def test_calculation_binding_requires_exact_calculation_and_requirement():
    from v2.contracts import TaskSpec,CalculationRequirement,DraftReport,Claim,VerifiedClaim,CalculationOutputBinding,DeclaredCalculation,DeclaredCalculationInput
    from v2.runtime.models import admit_verified_claim_bindings
    task=TaskSpec(goal="delta",mode="quick",deliverable="answer",calculation_requirements=[CalculationRequirement(id="delta",description="delta",requested_outputs=["PTS_DELTA"])])
    execution=_owned_execution();calc=DeclaredCalculation(calculation_id="c",requirement_id="delta",operation="subtract",inputs=[DeclaredCalculationInput(evidence_id="one",path="rows.WINS"),DeclaredCalculationInput(evidence_id="two",path="rows.LOSSES")],result="-7")
    binding=CalculationOutputBinding(requirement_id="delta",output_id="PTS_DELTA",calculation_id="c")
    claim=Claim(text="delta is -7",kind="derived",evidence_ids=["one","two"],calculation_id="c",output_bindings=[binding]);draft=DraftReport(sections=[],claims=[claim],calculations=[calc]);verified=VerifiedClaim(claim_index=0,claim=claim,evidence_ids=["one","two"],output_bindings=[binding])
    assert admit_verified_claim_bindings(task,execution,draft,verified) is verified
    wrong=CalculationOutputBinding(requirement_id="delta",output_id="PTS_DELTA",calculation_id="wrong")
    bad_claim=claim.model_copy(update={"calculation_id":"wrong","output_bindings":[wrong]})
    bad=VerifiedClaim(claim_index=0,claim=bad_claim,evidence_ids=["one","two"],output_bindings=[wrong])
    with pytest.raises(ValueError):admit_verified_claim_bindings(task,execution,draft,bad)

def _rank_admit(*, unit, result):
    from datetime import UTC,datetime
    from v2.contracts import CalculationRequirement,Claim,DraftReport,EvidenceEnvelope,Plan,PlanNode,TaskSpec,VerifiedClaim,CalculationOutputBinding,DeclaredCalculation,DeclaredCalculationInput
    from v2.runtime.models import ExecutionResult,admit_verified_claim_bindings
    task=TaskSpec(goal="rank",mode="quick",deliverable="rank",calculation_requirements=[CalculationRequirement(id="r",description="rank",requested_outputs=["RANK"])])
    envelope=EvidenceEnvelope(evidence_id="ev",capability="standings",source="fixture",observed_at=datetime.now(UTC),rows=[{"SCORE":119.5},{"SCORE":110.1}])
    execution=ExecutionResult(plan=Plan(nodes=[PlanNode(id="n",description="n",capability_hints=["standings"],status="complete")]),evidence_by_node={"n":envelope},attempts={"n":1})
    calc=DeclaredCalculation(calculation_id="rank1",requirement_id="r",operation="rank_desc",inputs=[DeclaredCalculationInput(evidence_id="ev",path="rows[0].SCORE"),DeclaredCalculationInput(evidence_id="ev",path="rows[1].SCORE")],result=str(result),unit=unit,subject_input=0)
    binding=CalculationOutputBinding(requirement_id="r",output_id="RANK",calculation_id="rank1")
    claim=Claim(text="rank is 1",kind="derived",evidence_ids=["ev"],calculation_id="rank1",output_bindings=[binding]);draft=DraftReport(sections=[],claims=[claim],calculations=[calc]);verified=VerifiedClaim(claim_index=0,claim=claim,evidence_ids=["ev"],output_bindings=[binding])
    return admit_verified_claim_bindings(task,execution,draft,verified)

def test_rank_calculation_with_rank_unit_admits():
    assert _rank_admit(unit="rank",result="1") is not None

@pytest.mark.parametrize("unit",[None,"unitless"])
def test_rank_calculation_with_unitless_admits(unit):
    assert _rank_admit(unit=unit,result="1") is not None

def test_rank_calculation_with_metric_unit_rejects():
    with pytest.raises(ValueError,match="rank calculation unit must be rank or unitless"):
        _rank_admit(unit="points_per_100_possessions",result="1")

def test_invented_rank_value_fails_recomputation():
    with pytest.raises(ValueError,match="did not pass recomputation"):
        _rank_admit(unit="rank",result="2")


def test_execution_and_binding_serialization_preserves_explicit_identity():
    from v2.contracts import Claim, EvidenceOutputBinding, VerifiedClaim
    from v2.runtime.models import ExecutionResult

    execution = _owned_execution(reordered=True, control=True)
    restored = ExecutionResult.model_validate_json(execution.model_dump_json())
    assert list(restored.evidence_by_node) == ["n2", "n1"]
    assert restored.evidence_by_node["n1"].evidence_id == "one"
    binding = EvidenceOutputBinding(value={"kind":"integer","value":0}, unit={"kind":"unitless"}, domain="standings",
        requirement_id="a", output_id="WINS", node_id="n1",
        evidence_id="one", selector="rows.WINS",
    )
    claim = Claim(
        text="zero", kind="observed", evidence_ids=["one"],
        output_bindings=[binding],
    )
    verified = VerifiedClaim(
        claim_index=0, claim=claim, evidence_ids=["one"],
        output_bindings=[binding],
    )
    assert VerifiedClaim.model_validate_json(
        verified.model_dump_json()) == verified

def test_verified_claim_authority_is_separate_from_untrusted_claim_proposal():
    from v2.contracts import Claim, EvidenceOutputBinding, VerifiedClaim

    binding = EvidenceOutputBinding(value={"kind":"integer","value":0}, unit={"kind":"unitless"}, domain="standings",
        requirement_id="a", output_id="WINS", node_id="n1",
        evidence_id="one", selector="rows.WINS",
    )
    claim = Claim(text="zero", kind="observed", evidence_ids=["one"],
                  output_bindings=[binding])
    verified = VerifiedClaim(
        claim_index=0, claim=claim, evidence_ids=["one"], output_bindings=[])
    assert verified.claim.output_bindings == [binding]
    assert verified.output_bindings == []

def test_binding_value_exactness_numeric_types_and_boolean_zero_distinction():
    from v2.contracts import (TaskSpec, EvidenceRequirement, DraftReport, Claim,
                              VerifiedClaim, EvidenceOutputBinding)
    from v2.runtime.models import admit_verified_claim_bindings
    task = TaskSpec(goal="wins", mode="quick", deliverable="answer",
        requirements=[EvidenceRequirement(id="a", description="wins",
            capability_options=["standings"], requested_outputs=["WINS","ACTIVE"])])
    execution = _owned_execution()
    def check(output, selector, value, unit):
        binding = EvidenceOutputBinding(requirement_id="a", output_id=output,
            node_id="n1", evidence_id="one", selector=selector, value=value,
            unit=unit, domain="standings")
        claim = Claim(text="value", kind="observed", evidence_ids=["one"],
                      output_bindings=[binding])
        return admit_verified_claim_bindings(task, execution,
            DraftReport(sections=[], claims=[claim]),
            VerifiedClaim(claim_index=0, claim=claim,
                evidence_ids=["one"], output_bindings=[binding]))
    assert check("WINS", "rows.WINS", {"kind":"integer","value":0},
                 {"kind":"declared","value":"count"})
    with pytest.raises(Exception):
        check("WINS", "rows.WINS", {"kind":"integer","value":"0"},
              {"kind":"declared","value":"count"})
    assert check("ACTIVE", "rows.ACTIVE", {"kind":"boolean","value":False},
                 {"kind":"unitless"})
    for value in [
        {"kind":"integer","value":99},
        {"kind":"string","value":"0"},
        {"kind":"boolean","value":False},
    ]:
        with pytest.raises(ValueError, match="value"):
            check("WINS", "rows.WINS", value,
                  {"kind":"declared","value":"count"})

def test_numeric_output_json_boundary_rejects_strings_and_roundtrips_numbers():
    import json
    from decimal import Decimal
    from v2.contracts import EvidenceOutputBinding
    base = dict(requirement_id="a", output_id="WINS", node_id="n1",
        evidence_id="one", selector="rows.WINS",
        unit={"kind":"declared","value":"count"}, domain="standings")
    for kind, raw in [("integer","0"), ("float","99"), ("integer",True)]:
        payload = dict(base, value={"kind":kind,"value":raw})
        with pytest.raises(Exception):
            EvidenceOutputBinding.model_validate_json(json.dumps(payload))
    cases = [
        {"kind":"integer","value":0},
        {"kind":"integer","value":10**200},
        {"kind":"float","value":1.5},
        {"kind":"decimal","value":"0.123456789123456789"},
        {"kind":"decimal","value":"1e+10000"},
        {"kind":"decimal","value":"1e-10000"},
        {"kind":"decimal","value":"-0"},
    ]
    for value in cases:
        binding = EvidenceOutputBinding(**dict(base, value=value))
        encoded = binding.model_dump_json()
        assert EvidenceOutputBinding.model_validate_json(encoded) == binding
        if value["kind"] == "decimal":
            assert binding.value.value == value["value"]
            assert Decimal(binding.value.value).is_finite()

def test_subject_selector_rejects_mixed_entity_id_and_allows_nested_metric():
    from datetime import UTC, datetime
    from v2.contracts import (TaskSpec, DraftReport, Claim, VerifiedClaim,
        EvidenceOutputBinding, EntityRef, EvidenceEnvelope, Plan, PlanNode)
    from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings
    lebron = EntityRef(id="23", type="player", display_name="LeBron")
    evidence = EvidenceEnvelope(evidence_id="mixed", capability="player_report",
        source="fixture", observed_at=datetime.now(UTC), entities=[lebron],
        rows=[{"PLAYER_ID":"30", "TEAM_ID":"23", "stats":{"PTS":25}}])
    execution = ExecutionResult(plan=Plan(nodes=[PlanNode(id="facts",
        description="facts", capability_hints=["player_report"], status="complete")]),
        evidence_by_node={"facts":evidence}, attempts={"facts":1})
    task = TaskSpec(goal="LeBron points", mode="quick", deliverable="answer",
                    requested_outputs=["PTS"], entities=[lebron])
    def validate(subject_selector):
        binding = EvidenceOutputBinding(requirement_kind="task", output_id="PTS",
            node_id="facts", evidence_id="mixed", selector="rows[0].stats.PTS",
            value={"kind":"integer","value":25}, unit={"kind":"unitless"},
            domain="player_report", subject_entity_type="player",
            subject_entity_id="23", subject_selector=subject_selector, row_selector="rows[0]")
        claim = Claim(text="points", kind="observed", evidence_ids=["mixed"],
                      output_bindings=[binding])
        return admit_verified_claim_bindings(task, execution,
            DraftReport(sections=[], claims=[claim]),
            VerifiedClaim(claim_index=0, claim=claim,
                evidence_ids=["mixed"], output_bindings=[binding]))
    with pytest.raises(ValueError, match="wrong entity type"):
        validate("rows[0].TEAM_ID")
    evidence.rows[0]["PLAYER_ID"] = "23"
    assert validate("rows[0].PLAYER_ID")

def test_numeric_variants_reject_cross_type_coercion_in_json_and_python():
    import json
    from v2.contracts import EvidenceOutputBinding
    base = dict(requirement_id="a", output_id="WINS", node_id="n1",
        evidence_id="one", selector="rows.WINS",
        unit={"kind":"declared","value":"count"}, domain="standings")
    bad = [
        {"kind":"float","value":1},
        {"kind":"integer","value":1.0},
        {"kind":"float","value":True},
        {"kind":"integer","value":False},
    ]
    for value in bad:
        with pytest.raises(Exception):
            EvidenceOutputBinding(**dict(base, value=value))
        with pytest.raises(Exception):
            EvidenceOutputBinding.model_validate_json(
                json.dumps(dict(base, value=value)))

def test_keyed_map_row_selector_blocks_sibling_and_prefix_tricks():
    from datetime import UTC, datetime
    from v2.contracts import (TaskSpec, DraftReport, Claim, VerifiedClaim,
        EvidenceOutputBinding, EntityRef, EvidenceEnvelope, Plan, PlanNode)
    from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings
    lebron = EntityRef(id="23", type="player", display_name="LeBron")
    curry = EntityRef(id="30", type="player", display_name="Curry")
    evidence = EvidenceEnvelope(evidence_id="pair", capability="player_report",
        source="fixture", observed_at=datetime.now(UTC), entities=[lebron,curry],
        rows={"lebron":{"PLAYER_ID":"23","stats":{"PTS":25}},
              "curry":{"PLAYER_ID":"30","stats":{"PTS":30}},
              "lebron_extra":{"PLAYER_ID":"30","stats":{"PTS":99}}})
    execution = ExecutionResult(plan=Plan(nodes=[PlanNode(id="pair",
        description="pair", capability_hints=["player_report"], status="complete")]),
        evidence_by_node={"pair":evidence}, attempts={"pair":1})
    task = TaskSpec(goal="LeBron", mode="quick", deliverable="answer",
                    requested_outputs=["PTS"], entities=[lebron])
    def validate(subject_selector, row_selector, selector="rows.lebron.stats.PTS"):
        binding = EvidenceOutputBinding(requirement_kind="task", output_id="PTS",
            node_id="pair", evidence_id="pair", selector=selector,
            row_selector=row_selector, value={"kind":"integer","value":25},
            unit={"kind":"unitless"}, domain="player_report",
            subject_entity_type="player", subject_entity_id="23",
            subject_selector=subject_selector)
        claim = Claim(text="25", kind="observed", evidence_ids=["pair"],
                      output_bindings=[binding])
        return admit_verified_claim_bindings(task, execution,
            DraftReport(sections=[], claims=[claim]), VerifiedClaim(
                claim_index=0, claim=claim, evidence_ids=["pair"],
                output_bindings=[binding]))
    assert validate("rows.lebron.PLAYER_ID", "rows.lebron")
    with pytest.raises(ValueError, match="direct row child"):
        validate("rows.curry.PLAYER_ID", "rows.lebron")
    with pytest.raises(ValueError, match="direct row child"):
        validate("rows.lebron_extra.PLAYER_ID", "rows.lebron")

def test_broad_row_selector_cannot_join_sibling_subject_and_metric():
    from datetime import UTC, datetime
    from v2.contracts import (TaskSpec, DraftReport, Claim, VerifiedClaim,
        EvidenceOutputBinding, EntityRef, EvidenceEnvelope, Plan, PlanNode)
    from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings
    lebron = EntityRef(id="23", type="player", display_name="LeBron")
    def reject(rows, selector, subject_selector, row_selector):
        evidence = EvidenceEnvelope(evidence_id="ev", capability="player_report",
            source="fixture", observed_at=datetime.now(UTC), entities=[lebron], rows=rows)
        execution = ExecutionResult(plan=Plan(nodes=[PlanNode(id="facts",
            description="facts", capability_hints=["player_report"], status="complete")]),
            evidence_by_node={"facts":evidence}, attempts={"facts":1})
        binding = EvidenceOutputBinding(requirement_kind="task", output_id="PTS",
            node_id="facts", evidence_id="ev", selector=selector,
            row_selector=row_selector, value={"kind":"integer","value":25},
            unit={"kind":"unitless"}, domain="player_report",
            subject_entity_type="player", subject_entity_id="23",
            subject_selector=subject_selector)
        claim = Claim(text="25", kind="observed", evidence_ids=["ev"],
                      output_bindings=[binding])
        with pytest.raises(ValueError, match="direct row child"):
            admit_verified_claim_bindings(TaskSpec(goal="x",mode="quick",
                deliverable="x",requested_outputs=["PTS"],entities=[lebron]),
                execution, DraftReport(sections=[],claims=[claim]), VerifiedClaim(
                    claim_index=0,claim=claim,evidence_ids=["ev"],output_bindings=[binding]))
    reject({"lebron":{"PLAYER_ID":"30","stats":{"PTS":25}},
            "curry":{"PLAYER_ID":"23","stats":{"PTS":30}}},
           "rows.lebron.stats.PTS", "rows.curry.PLAYER_ID", "rows")
    reject([{"PLAYER_ID":"30","stats":{"PTS":25}},
            {"PLAYER_ID":"23","stats":{"PTS":30}}],
           "rows[0].stats.PTS", "rows[1].PLAYER_ID", "rows")


@pytest.fixture
def anyio_backend():
    return "asyncio"
