import pytest


def test_wrong_season_evidence_is_rejected():
    from datetime import UTC, date, datetime

    from v2.contracts import (
        Claim,
        ClaimKind,
        DraftReport,
        EntityRef,
        EvidenceEnvelope,
        RunMode,
        SeasonRef,
        TaskSpec,
    )
    from v2.runtime.verifier import verify_mechanical

    task = TaskSpec(
        goal="Rank Boston", mode=RunMode.QUICK, deliverable="answer",
        entities=[EntityRef(
            id="BOS", type="team", display_name="Capital City Stars")],
        season=SeasonRef(value="2025-26", source="user", confidence=1),
        as_of=date(2026, 4, 15))
    envelope = EvidenceEnvelope(
        evidence_id="standings", capability="standings",
        source="warehouse:standings",
        observed_at=datetime(2026, 4, 15, 12, tzinfo=UTC),
        season="2024-25", as_of=date(2026, 4, 15),
        entities=[EntityRef(
            id="BOS", type="team", display_name="Capital City Stars")],
        rows=[{"TEAM": "Capital City Stars", "W": 61}],
        units={"W": "count"})
    claim = Claim(
        text="The Capital City Stars had 61 wins in 2025-26.",
        kind=ClaimKind.OBSERVED, evidence_ids=["standings"])
    reasons = verify_mechanical(
        task, DraftReport(sections=[claim.text], claims=[claim]),
        [envelope]).claim_results[0].reasons
    assert any("does not match task season" in reason for reason in reasons)
