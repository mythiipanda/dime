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
