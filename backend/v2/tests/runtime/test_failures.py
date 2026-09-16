from v2.runtime.failures import CandidateState, CandidateStore, FailureObservation


def observation(summary="mixed provenance"):
    return FailureObservation(
        source="qa", failure_class="source_provenance",
        summary=summary, expected_relation="label each claim's source",
        revision="bad123", trace_id="trace-1")


def test_failure_observation_becomes_reviewable_sanitized_candidate(tmp_path):
    store = CandidateStore(tmp_path / "candidates.jsonl")
    candidate = store.add(observation())
    assert candidate.state == CandidateState.PENDING
    assert candidate.first_bad_revision == "bad123"
    assert candidate.trace_id == "trace-1"
    assert len(candidate.candidate_id) == 24


def test_candidate_intake_deduplicates_same_failure_shape(tmp_path):
    store = CandidateStore(tmp_path / "candidates.jsonl")
    first = store.add(observation("Mixed   provenance"))
    second = store.add(observation("mixed provenance"))
    assert first.candidate_id == second.candidate_id
    assert store.read() == [first]


def test_failure_intake_contracts_reject_unknown_fields() -> None:
    import pytest
    from pydantic import ValidationError
    from v2.runtime.failures import ScenarioCandidate

    with pytest.raises(ValidationError, match="invented"):
        FailureObservation.model_validate({
            "source": "qa", "failure_class": "grounding", "summary": "wrong",
            "expected_relation": "cite source", "revision": "bad", "invented": True,
        })
    with pytest.raises(ValidationError, match="invented"):
        ScenarioCandidate.model_validate({
            "candidate_id": "id", "source": "qa", "failure_class": "grounding",
            "summary": "wrong", "expected_relation": "cite source",
            "first_bad_revision": "bad", "invented": True,
        })
