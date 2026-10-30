from datetime import UTC, datetime

import pytest

from v2.contracts import (
    Claim,
    ClaimKind,
    DraftReport,
    EntityRef,
    EvidenceEnvelope,
    RunMode,
    SeasonRef,
    TaskSpec,
    VerificationStatus,
)
from v2.runtime.verifier import verify_mechanical

PLAYER = EntityRef(id="9999", type="player", display_name="Test Player")

def _task() -> TaskSpec:
    return TaskSpec(
        goal="Season scoring average for Test Player",
        mode=RunMode.QUICK,
        deliverable="points per game",
        entities=[PLAYER],
        season=SeasonRef(value="2025-26", source="user", confidence=1.0),
    )

def _evidence(rows: list[dict], units: dict[str, str]) -> EvidenceEnvelope:
    return EvidenceEnvelope(
        evidence_id="scoring",
        capability="player_report",
        source="warehouse:get_player_report",
        observed_at=datetime(2026, 4, 15, 12, tzinfo=UTC),
        season="2025-26",
        entities=[PLAYER],
        rows=rows,
        units=units,
        qualification="Full regular-season player line",
        coverage="All players represented in the selected season",
    )

def _report(text: str) -> DraftReport:
    claim = Claim(
        text=text, kind=ClaimKind.OBSERVED, evidence_ids=["scoring"])
    return DraftReport(sections=[text], claims=[claim])

def test_zero_ppg_without_scoring_totals_is_rejected_and_names_player():
    envelope = _evidence(
        [{"PLAYER_ID": 9999, "PLAYER": "Test Player", "GP": 20, "PPG": 0.0}],
        {"GP": "count", "PPG": "per_game"},
    )
    result = verify_mechanical(
        _task(),
        _report("Test Player averaged 0.0 points per game in 2025-26."),
        [envelope],
    )
    assert result.status == VerificationStatus.REPAIR
    reasons = result.claim_results[0].reasons
    assert any("Test Player" in reason and "PPG" in reason
               for reason in reasons)

def test_genuine_scoreless_line_with_zero_totals_passes():
    envelope = _evidence(
        [{"PLAYER_ID": 9999, "PLAYER": "Test Player", "GP": 5,
          "PTS": 0, "PPG": 0.0, "MIN": 60}],
        {"GP": "count", "PTS": "count", "PPG": "per_game",
         "MIN": "minutes"},
    )
    result = verify_mechanical(
        _task(),
        _report("Test Player averaged 0.0 points per game in 2025-26."),
        [envelope],
    )
    assert result.status == VerificationStatus.PASS

def test_nonzero_scoring_line_is_unaffected():
    envelope = _evidence(
        [{"PLAYER_ID": 9999, "PLAYER": "Test Player", "GP": 20,
          "PTS": 500, "PPG": 25.0, "MIN": 600}],
        {"GP": "count", "PTS": "count", "PPG": "per_game",
         "MIN": "minutes"},
    )
    result = verify_mechanical(
        _task(),
        _report("Test Player averaged 25.0 points per game in 2025-26."),
        [envelope],
    )
    assert result.status == VerificationStatus.PASS

def test_zero_in_a_non_scoring_metric_is_unaffected():
    envelope = _evidence(
        [{"PLAYER_ID": 9999, "PLAYER": "Test Player", "GP": 20,
          "TOV": 0.0}],
        {"GP": "count", "TOV": "count"},
    )
    result = verify_mechanical(
        _task(),
        _report("Test Player averaged 0.0 turnovers per game in 2025-26."),
        [envelope],
    )
    assert result.status == VerificationStatus.PASS
