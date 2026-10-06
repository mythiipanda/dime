import json
from pathlib import Path

from v2.contracts import (
    DraftReport,
    EntityRef,
    EvidenceEnvelope,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
)
from v2.runtime.verifier import (
    merge_verification_reports,
    verify_mechanical,
)

RECORDING = (
    Path(__file__).with_name("fixtures") / "assists_leader_rejected.jsonl"
)

def _frames():
    return [
        json.loads(line)
        for line in RECORDING.read_text().splitlines()
        if line.strip()
    ]

def _recording():
    frames = _frames()
    task = TaskSpec.model_validate(
        next(frame for frame in frames if frame["kind"] == "tool/call")["data"]["task"]
    )
    evidence = [
        EvidenceEnvelope.model_validate(frame["data"]["evidence"])
        for frame in frames
        if frame["kind"] == "tool/result"
    ]
    drafts = [
        DraftReport.model_validate(frame["data"]["output"])
        for frame in frames
        if frame["kind"] == "assistant/attempt"
    ]
    return task, evidence, drafts

def _row(envelope, key):
    return envelope.rows[0][key]

def _minutes_metric(envelope):
    return next(
        metric for metric, unit in envelope.units.items()
        if unit == "minutes"
    )

def _unit_of(envelope, metric):
    return envelope.units[metric]

def _leaderboard_of(envelope):
    leader = next(
        entity for entity in envelope.entities
        if entity.display_name == envelope.rows[0]["PLAYER"]
    )
    return envelope.model_copy(update={
        "entities": [leader],
        "rows": [envelope.rows[0]],
    })

def _claim(text, evidence_ids):
    from v2.contracts import Claim
    return Claim(text=text, kind="observed", evidence_ids=list(evidence_ids))

def _draft(claim):
    return DraftReport(sections=[claim.text], claims=[claim])

def test_recorded_answer_with_every_number_in_evidence_passes_with_zero_repairs():
    task, evidence, drafts = _recording()

    result = verify_mechanical(task, drafts[0], evidence)

    assert result.status == VerificationStatus.PASS
    assert result.repair_instructions == []
    assert [item.supported for item in result.claim_results] == [True]
    assert [item.reasons for item in result.claim_results] == [[]]

def test_competition_reference_is_not_an_unsupported_entity_claim():
    task, evidence, drafts = _recording()

    result = verify_mechanical(task, drafts[0], evidence)

    assert not any(
        "is not supported by cited evidence" in reason
        for reason in result.claim_results[0].reasons
    )
    assert not any(
        "is not supported by cited evidence" in repair
        for repair in result.repair_instructions
    )

def test_metric_name_inside_an_ordinary_word_is_not_that_metric():
    task, evidence, _ = _recording()
    envelope = evidence[0]
    metric = _minutes_metric(envelope)
    unit = _unit_of(envelope, metric)
    claim = _claim(
        f"{envelope.rows[0]['PLAYER']} posted {_row(envelope, metric)} "
        f"{envelope.season} leaderboard {metric}imums.",
        [envelope.evidence_id],
    )

    reasons = verify_mechanical(task, _draft(claim), [envelope]).claim_results[0].reasons

    assert not any(unit in reason for reason in reasons)

def test_metric_named_on_a_word_boundary_without_its_unit_is_rejected():
    task, evidence, _ = _recording()
    envelope = evidence[0]
    metric = _minutes_metric(envelope)
    unit = _unit_of(envelope, metric)
    claim = _claim(
        f"{envelope.rows[0]['PLAYER']} logged {_row(envelope, metric)} "
        f"{metric} across {_row(envelope, 'GP')} games in {envelope.season}.",
        [envelope.evidence_id],
    )

    result = verify_mechanical(task, _draft(claim), [envelope])

    assert result.status == VerificationStatus.REPAIR
    assert f"metric {metric} is stated without its declared unit {unit}" in (
        result.claim_results[0].reasons
    )

def test_entity_absent_from_cited_evidence_is_still_rejected():
    task, evidence, _ = _recording()
    leaderboard = evidence[0]
    narrow = _leaderboard_of(leaderboard)
    named = next(
        entity for entity in leaderboard.entities
        if entity.display_name != narrow.rows[0]["PLAYER"]
    )
    scoped = task.model_copy(update={"entities": [named]})
    claim = _claim(
        f"{named.display_name} led with {_row(leaderboard, 'AST')} assists "
        f"over {_row(leaderboard, 'GP')} games in {leaderboard.season}.",
        [narrow.evidence_id],
    )

    result = verify_mechanical(scoped, _draft(claim), [narrow])

    assert result.status == VerificationStatus.REPAIR
    assert f"entity {named.display_name} is not supported by cited evidence" in (
        result.claim_results[0].reasons
    )

def test_generator_verdict_cannot_clear_a_mechanical_repair():
    task, evidence, _ = _recording()
    envelope = evidence[0]
    metric = _minutes_metric(envelope)
    claim = _claim(
        f"{envelope.rows[0]['PLAYER']} logged {_row(envelope, metric)} "
        f"{metric} across {_row(envelope, 'GP')} games in {envelope.season}.",
        [envelope.evidence_id],
    )
    mechanical = verify_mechanical(task, _draft(claim), [envelope])
    generator = VerificationReport(status=VerificationStatus.PASS, claim_results=[
        {"claim_index": 0, "supported": True, "reasons": []}])

    merged = merge_verification_reports(mechanical, generator)

    assert mechanical.status == VerificationStatus.REPAIR
    assert merged.status == VerificationStatus.REPAIR
    assert merged.claim_results[0].supported is False
    assert merged.claim_results[0].reasons == mechanical.claim_results[0].reasons

def test_league_entity_task_still_requires_evidence_for_named_players():
    task, evidence, _ = _recording()
    envelope = _leaderboard_of(evidence[0])
    absent = next(
        entity for entity in evidence[0].entities
        if entity.display_name != envelope.rows[0]["PLAYER"]
    )
    scoped = task.model_copy(update={
        "entities": [*task.entities, EntityRef(
            id=absent.id, type=absent.type, display_name=absent.display_name)],
    })
    claim = _claim(
        f"{absent.display_name} led with {_row(envelope, 'AST')} assists "
        f"over {_row(envelope, 'GP')} games in {envelope.season}.",
        [envelope.evidence_id],
    )

    result = verify_mechanical(scoped, _draft(claim), [envelope])

    assert result.status == VerificationStatus.REPAIR
    assert f"entity {absent.display_name} is not supported by cited evidence" in (
        result.claim_results[0].reasons
    )