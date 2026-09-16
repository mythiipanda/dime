import pytest
from v2.runtime.shadow import (
    DifferenceKind, RunOutcome, ShadowStore, compare_outcomes,
)


def outcome(**updates):
    values = {
        "status": "ok", "answer": "Boston won 61 games.",
        "capabilities": ["standings"], "evidence_count": 1,
        "supported_claims": 1, "total_claims": 1,
    }
    values.update(updates)
    return RunOutcome(**values)


def test_shadow_comparison_validates_request_boundary():
    for request in (" ", "x" * 2001):
        with pytest.raises(ValueError, match="shadow request"):
            compare_outcomes(request, outcome(), outcome())
    with pytest.raises(TypeError, match="shadow request"):
        compare_outcomes(7, outcome(), outcome())


def test_equal_outcomes_have_no_differences_and_hide_request():
    comparison = compare_outcomes("What is Boston's record?", outcome(), outcome())
    assert comparison.differences == []
    assert "Boston's" not in comparison.model_dump_json()
    assert len(comparison.request_hash) == 64


def test_ok_shadow_outcome_cannot_encode_blank_success():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="non-empty answer"):
        outcome(answer=" ")


def test_comparison_classifies_answer_route_grounding_and_failure():
    comparison = compare_outcomes(
        "record?", outcome(), outcome(
            status="partial", answer="I could not verify it.",
            capabilities=["metric_coverage"], evidence_count=0,
            supported_claims=0))
    assert comparison.differences == [
        DifferenceKind.FAILURE, DifferenceKind.ANSWER,
        DifferenceKind.ROUTE, DifferenceKind.GROUNDING,
    ]



def test_grounding_drift_requires_comparable_claim_metrics():
    comparison = compare_outcomes(
        "record?",
        outcome(evidence_count=1, supported_claims=None, total_claims=None),
        outcome(evidence_count=3, supported_claims=3, total_claims=3),
    )
    assert DifferenceKind.GROUNDING not in comparison.differences

    comparable = compare_outcomes(
        "record?",
        outcome(status="partial", evidence_count=1,
                supported_claims=1, total_claims=2),
        outcome(status="partial", evidence_count=3,
                supported_claims=2, total_claims=2),
    )
    assert DifferenceKind.GROUNDING in comparable.differences

def test_equal_non_ok_outcomes_remain_failure_drift() -> None:
    comparison = compare_outcomes(
        "record?", outcome(status="partial"), outcome(status="partial"))
    assert comparison.differences == [DifferenceKind.FAILURE]


def test_shadow_store_is_append_only(tmp_path):
    store = ShadowStore(tmp_path / "shadow.jsonl")
    comparison = compare_outcomes("record?", outcome(), outcome())
    store.append(comparison)
    store.append(comparison)
    assert store.read() == [comparison, comparison]


def test_shadow_gate_requires_volume_and_bounded_drift():
    from v2.runtime.shadow import ShadowGatePolicy, evaluate_shadow_gate

    equal = compare_outcomes("record?", outcome(), outcome())
    answer_drift = compare_outcomes(
        "other?", outcome(), outcome(answer="different"))
    policy = ShadowGatePolicy(
        minimum_runs=2, maximum_failure_rate=0,
        maximum_grounding_drift_rate=0, maximum_route_drift_rate=0,
        maximum_answer_drift_rate=.5)
    report = evaluate_shadow_gate([equal, answer_drift], policy)
    assert report.ready
    assert report.answer_drift_rate == .5


def test_shadow_gate_counts_repeated_equal_runs():
    from v2.runtime.shadow import ShadowGatePolicy, evaluate_shadow_gate

    comparison = compare_outcomes("record?", outcome(), outcome())
    report = evaluate_shadow_gate(
        [comparison, comparison], ShadowGatePolicy(minimum_runs=2))
    assert report.ready
    assert report.total_runs == 2


def test_shadow_gate_reports_every_failed_threshold():
    from v2.runtime.shadow import ShadowGatePolicy, evaluate_shadow_gate

    drift = compare_outcomes(
        "record?", outcome(), outcome(
            status="partial", answer="different",
            capabilities=["other"], evidence_count=0,
            supported_claims=0))
    report = evaluate_shadow_gate(
        [drift], ShadowGatePolicy(
            minimum_runs=2, maximum_failure_rate=0,
            maximum_grounding_drift_rate=0, maximum_route_drift_rate=0,
            maximum_answer_drift_rate=0))
    assert not report.ready
    assert len(report.blockers) == 5
    assert report.blockers[0] == "need 1 more shadow runs"


def test_shadow_persisted_contracts_reject_unknown_fields() -> None:
    import pytest
    from pydantic import ValidationError
    from v2.runtime.shadow import ShadowComparison, ShadowGatePolicy, ShadowGateReport

    with pytest.raises(ValidationError, match="invented"):
        RunOutcome.model_validate({
            "status": "ok", "invented": True,
        })
    with pytest.raises(ValidationError, match="invented"):
        ShadowComparison.model_validate({
            "comparison_id": "id", "request_hash": "hash",
            "v1": {"status": "ok"}, "v2": {"status": "ok"},
            "invented": True,
        })
    with pytest.raises(ValidationError, match="invented"):
        ShadowGatePolicy.model_validate({"invented": True})
    with pytest.raises(ValidationError, match="invented"):
        ShadowGateReport.model_validate({
            "total_runs": 0, "failure_rate": 0, "grounding_drift_rate": 0,
            "route_drift_rate": 0, "answer_drift_rate": 0, "ready": False,
            "invented": True,
        })


def test_shadow_outcome_rejects_unknown_status() -> None:
    import pytest
    from pydantic import ValidationError

    for status in ("", "success", "PASS"):
        with pytest.raises(ValidationError, match="Input should be"):
            outcome(status=status)


def test_shadow_claim_metrics_are_jointly_known_or_unknown() -> None:
    from pydantic import ValidationError

    assert outcome(supported_claims=None, total_claims=None).total_claims is None
    with pytest.raises(ValidationError, match="both be known or unknown"):
        outcome(supported_claims=None, total_claims=1)


def test_ok_shadow_outcome_rejects_incomplete_claim_support() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="every claim"):
        outcome(status="ok", supported_claims=0, total_claims=1)


def test_shadow_comparison_rejects_bad_identity_and_duplicate_differences() -> None:
    import pytest
    from pydantic import ValidationError
    from v2.runtime.shadow import ShadowComparison

    valid = compare_outcomes("request", outcome(), outcome())
    base = valid.model_dump(mode="python")
    for changes, error in [
        ({"comparison_id": " "}, "identity"),
        ({"request_hash": "hash"}, "lowercase sha256"),
        ({"differences": ["answer", "answer"]}, "differences must be unique"),
    ]:
        with pytest.raises(ValidationError, match=error):
            ShadowComparison(**{**base, **changes})


def test_shadow_gate_report_rejects_impossible_state() -> None:
    import pytest
    from pydantic import ValidationError
    from v2.runtime.shadow import ShadowGateReport

    base = {"total_runs": 1, "failure_rate": 0, "grounding_drift_rate": 0,
            "route_drift_rate": 0, "answer_drift_rate": 0, "ready": True}
    for changes, error in [
        ({"failure_rate": 1.1}, "out of range"),
        ({"total_runs": -1}, "out of range"),
        ({"ready": False, "blockers": []}, "contradicts"),
        ({"ready": True, "blockers": ["blocked"]}, "contradicts"),
        ({"ready": False, "blockers": ["same", "same"]}, "must be unique"),
    ]:
        with pytest.raises(ValidationError, match=error):
            ShadowGateReport(**{**base, **changes})


def test_v2_outcome_preserves_nonpassing_verification_status() -> None:
    from v2.contracts import DraftReport, Plan, TaskSpec, VerificationReport
    from v2.runtime.models import ExecutionResult, RuntimeResult
    from v2.runtime.shadow import outcome_from_v2

    result = RuntimeResult(
        task=TaskSpec(goal="answer", mode="quick", deliverable="text"),
        execution=ExecutionResult(plan=Plan(nodes=[])),
        draft=DraftReport(sections=["No answer"], claims=[]),
        verification=VerificationReport(status="partial"),
        gaps=[{"kind": "missing_evidence", "message": "missing"}],
    )
    v2_outcome = outcome_from_v2(result, "missing")
    assert v2_outcome.status == "partial"
    comparison = compare_outcomes("answer?", outcome(status="ok"), v2_outcome)
    assert DifferenceKind.FAILURE in comparison.differences


def test_shadow_store_serializes_independent_writers(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "shadow.jsonl"
    comparisons = [compare_outcomes(f"request {index}", outcome(), outcome())
                   for index in range(20)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda item: ShadowStore(path).append(item), comparisons))
    assert {item.comparison_id for item in ShadowStore(path).read()} == {
        item.comparison_id for item in comparisons
    }


def test_shadow_store_rejects_blank_persisted_records(tmp_path):
    import pytest

    path = tmp_path / "shadow.jsonl"
    store = ShadowStore(path)
    store.append(compare_outcomes("request", outcome(), outcome()))
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="blank records"):
        store.read()


def test_shadow_comparison_rejects_forged_derived_fields() -> None:
    import pytest
    from pydantic import ValidationError
    from v2.runtime.shadow import ShadowComparison

    comparison = compare_outcomes("request", outcome(), outcome(answer="different"))
    payload = comparison.model_dump(mode="python")
    with pytest.raises(ValidationError, match="differences do not match"):
        ShadowComparison.model_validate({**payload, "differences": []})
    with pytest.raises(ValidationError, match="comparison id does not match"):
        ShadowComparison.model_validate({**payload, "comparison_id": "0" * 24})


def test_v2_outcome_deduplicates_reused_capability_route() -> None:
    from datetime import UTC, datetime
    from v2.contracts import (Claim, ClaimResult, DraftReport, EvidenceEnvelope,
                              Plan, PlanNode, TaskSpec, VerificationReport)
    from v2.runtime.models import ExecutionResult, RuntimeResult
    from v2.runtime.shadow import outcome_from_v2

    evidence = [
        EvidenceEnvelope(
            evidence_id=f"ev-{index}", capability="player_report",
            source="fixture", observed_at=datetime.now(UTC), rows={"index": index},
        )
        for index in range(2)
    ]
    claims = [Claim(text=f"Fact {index}.", kind="observed",
                    evidence_ids=[item.evidence_id])
              for index, item in enumerate(evidence)]
    result = RuntimeResult(
        task=TaskSpec(goal="answer", mode="quick", deliverable="text"),
        execution=ExecutionResult(
            plan=Plan(nodes=[PlanNode(
                id=f"node-{index}", description="facts",
                capability_hints=["player_report"], status="complete")
                for index in range(2)]),
            evidence=evidence, attempts={f"node-{index}": 1 for index in range(2)},
        ),
        draft=DraftReport(sections=["Answer"], claims=claims),
        verification=VerificationReport(status="pass", claim_results=[
            ClaimResult(claim_index=index, supported=True) for index in range(2)]),
        verified_claims=[{
            "claim_index": index, "claim": claim,
            "evidence_ids": claim.evidence_ids,
            "sources": [{"evidence_id": item.evidence_id,
                         "source": item.source,
                         "capability": item.capability}],
        } for index, (claim, item) in enumerate(zip(claims, evidence, strict=True))],
    )
    assert outcome_from_v2(result, "answer").capabilities == ["player_report"]


def test_v2_outcome_revalidates_runtime_result() -> None:
    from v2.runtime.shadow import outcome_from_v2

    invalid = outcome(status="partial")
    with pytest.raises(Exception):
        outcome_from_v2(invalid, "answer")


def test_shadow_store_rejects_symlinked_record(tmp_path):
    import pytest

    outside = tmp_path / "outside.jsonl"
    outside.write_text("")
    path = tmp_path / "shadow.jsonl"
    path.symlink_to(outside)
    with pytest.raises(ValueError, match="cannot be a symlink"):
        ShadowStore(path)
    assert outside.read_text() == ""


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_shadow_gate_report_rejects_nonfinite_rates(value) -> None:
    from pydantic import ValidationError
    from v2.runtime.shadow import ShadowGateReport

    with pytest.raises(ValidationError, match="rates are out of range"):
        ShadowGateReport(
            total_runs=1, failure_rate=value, grounding_drift_rate=0,
            route_drift_rate=0, answer_drift_rate=0, ready=True,
        )


@pytest.mark.parametrize("field", [
    "evidence_count", "supported_claims", "total_claims", "duration_ms",
])
def test_shadow_outcome_rejects_boolean_counts(field) -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        outcome(**{field: True})


def test_shadow_gate_counts_reject_booleans() -> None:
    from pydantic import ValidationError
    from v2.runtime.shadow import ShadowGatePolicy, ShadowGateReport
    with pytest.raises(ValidationError):
        ShadowGatePolicy(minimum_runs=True)
    with pytest.raises(ValidationError):
        ShadowGateReport(
            total_runs=True, failure_rate=0, grounding_drift_rate=0,
            route_drift_rate=0, answer_drift_rate=0, ready=True,
        )


def test_shadow_store_rejects_symlinked_parent(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    parent = tmp_path / "parent"
    parent.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="parent cannot be a symlink"):
        ShadowStore(parent / "shadow.jsonl")


@pytest.mark.parametrize("field_name", [
    "maximum_failure_rate", "maximum_grounding_drift_rate",
    "maximum_route_drift_rate", "maximum_answer_drift_rate",
])
def test_shadow_policy_rates_are_strict_floats(field_name) -> None:
    from pydantic import ValidationError
    from v2.runtime.shadow import ShadowGatePolicy
    with pytest.raises(ValidationError):
        ShadowGatePolicy(**{field_name: "0.1"})


def test_shadow_gate_revalidates_copied_policy() -> None:
    from pydantic import ValidationError
    from v2.runtime.shadow import ShadowGatePolicy, evaluate_shadow_gate
    unsafe = ShadowGatePolicy().model_copy(
        update={"maximum_failure_rate": float("nan")})
    with pytest.raises(ValidationError, match="less than or equal"):
        evaluate_shadow_gate([], unsafe)


def test_shadow_gate_revalidates_copied_comparisons() -> None:
    from pydantic import ValidationError
    from v2.runtime.shadow import compare_outcomes, evaluate_shadow_gate
    valid = compare_outcomes("request", outcome(), outcome())
    unsafe = valid.model_copy(update={"differences": [DifferenceKind.ANSWER]})
    with pytest.raises(ValidationError, match="do not match recorded outcomes"):
        evaluate_shadow_gate([unsafe])


def test_shadow_store_revalidates_copied_comparison(tmp_path):
    from pydantic import ValidationError
    valid = compare_outcomes("request", outcome(), outcome())
    unsafe = valid.model_copy(update={"comparison_id": "bad"})
    with pytest.raises(ValidationError, match="does not match recorded outcomes"):
        ShadowStore(tmp_path / "shadow.jsonl").append(unsafe)
    assert not (tmp_path / "shadow.jsonl").exists()


def test_compare_outcomes_revalidates_copied_inputs() -> None:
    from pydantic import ValidationError
    invalid = outcome().model_copy(update={"supported_claims": -1})
    with pytest.raises(ValidationError, match="non-negative"):
        compare_outcomes("request", invalid, outcome())
