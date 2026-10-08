from __future__ import annotations

import pytest
from v2.contracts import (
    ArtifactIntent,
    ArtifactPoint,
    ArtifactSeries,
    Claim,
    ClaimKind,
    DraftReport,
    EvidenceEnvelope,
)

@pytest.fixture
def anyio_backend():
    return "asyncio"

def _envelope() -> EvidenceEnvelope:
    from datetime import UTC, datetime
    return EvidenceEnvelope(
        evidence_id="game_logs:g1",
        capability="game_logs",
        source="v1:get_game_logs:warehouse",
        observed_at=datetime.now(UTC),
        rows={"2025-01-01": {"points": 30}, "2025-01-05": {"points": 22}},
    )

def test_an_intent_names_series_and_points_not_values() -> None:
    intent = ArtifactIntent(
        id="trend",
        kind="chart",
        title="Scoring trend",
        series=[ArtifactSeries(
            name="Shai Gilgeous-Alexander",
            points=[ArtifactPoint(x="2025-01-01", output_id="PTS")])],
    )

    assert intent.series[0].points[0].output_id == "PTS"
    assert not hasattr(intent.series[0].points[0], "value")

def test_an_intent_rejects_a_kind_the_frontend_cannot_render() -> None:
    with pytest.raises(ValueError):
        ArtifactIntent(id="x", kind="pie", title="x", series=[])

def test_a_draft_may_carry_artifacts() -> None:
    draft = DraftReport(
        sections=["Trend"],
        claims=[],
        artifacts=[ArtifactIntent(
            id="trend", kind="chart", title="Trend",
            series=[ArtifactSeries(name="SGA", points=[
                ArtifactPoint(x="2025-01-01", output_id="PTS")])])],
    )

    assert draft.artifacts[0].kind == "chart"

def test_a_claim_may_carry_the_intent_id_it_is_drawn_from() -> None:
    claim = Claim(
        text="Scoring trend", kind=ClaimKind.OBSERVED,
        evidence_ids=["game_logs:g1"], artifact_id="trend",
    )

    assert claim.artifact_id == "trend"