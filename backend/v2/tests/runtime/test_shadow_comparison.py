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


def test_equal_outcomes_have_no_differences_and_hide_request():
    comparison = compare_outcomes("What is Boston's record?", outcome(), outcome())
    assert comparison.differences == []
    assert "Boston's" not in comparison.model_dump_json()
    assert len(comparison.request_hash) == 64


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
