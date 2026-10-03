from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from v2.api.routes import _answer_text
from v2.contracts import EvidenceEnvelope, EvidenceOutputBinding, OutputFinalStatus

AS_OF = date(2026, 10, 3)
WAREHOUSE_AS_OF = date(2026, 4, 14)


def _envelope(evidence_id: str, *, identity: dict, as_of: date | None, source: str) -> EvidenceEnvelope:
    return EvidenceEnvelope(
        evidence_id=evidence_id,
        capability="team_ratings",
        source=source,
        observed_at=datetime(2026, 10, 3, 12, tzinfo=UTC),
        season="2024-25",
        as_of=as_of,
        rows=[{"OFF_RATING": 119.5, "DEF_RATING": 110.1, "NET_RATING": 9.4}],
        source_identity=identity,
    )


def _result(*envelopes: EvidenceEnvelope) -> SimpleNamespace:
    binding = EvidenceOutputBinding(
        requirement_id="ratings",
        output_id="NET_RATING",
        node_id="ratings",
        evidence_id=envelopes[0].evidence_id,
        selector="rows[0].NET_RATING",
        value={"kind": "decimal", "value": "9.4"},
        unit={"kind": "declared", "value": "net_rating"},
        domain="team_ratings",
    )
    return SimpleNamespace(
        output_statuses=[OutputFinalStatus(
            requirement_kind="evidence", requirement_id="ratings",
            output_id="NET_RATING", status="complete", claim_index=0,
            binding=binding)],
        verified_claims=[],
        gaps=[],
        execution=SimpleNamespace(evidence=list(envelopes)),
    )


LIVE_ONLY_LINE = (
    "These figures came from the NBA's live feed on 2026-10-03, not from the "
    "figures I had saved, so they can differ from numbers you saw earlier."
)


def test_live_sourced_answer_states_the_source_and_the_date() -> None:
    result = _result(_envelope(
        "live", identity={"kind": "live", "source": "nba_api"},
        as_of=AS_OF, source="silver:team_ratings:nba_api"))

    lines = _answer_text(result).splitlines()
    assert len(lines) == 2
    assert lines[0].endswith("NET_RATING = 9.4 (net_rating)")
    assert lines[1] == LIVE_ONLY_LINE


def test_warehouse_sourced_answer_carries_no_live_label() -> None:
    result = _result(_envelope(
        "stored", identity={"kind": "warehouse", "warehouse_id": "configured-runtime",
                            "sha256": "0" * 64},
        as_of=WAREHOUSE_AS_OF, source="silver:team_ratings:warehouse"))

    text = _answer_text(result)
    assert text.splitlines() == [
        "NET_RATING = 9.4 (net_rating)"]
    assert "live" not in text
    assert "2026-04-14" not in text


def test_restated_answer_separates_the_refreshed_figures_from_the_saved_ones() -> None:
    result = _result(
        _envelope("stored", identity={"kind": "warehouse", "warehouse_id": "configured-runtime",
                                      "sha256": "0" * 64},
                  as_of=WAREHOUSE_AS_OF, source="silver:team_ratings:warehouse"),
        _envelope("live", identity={"kind": "composite", "warehouse_id": "configured-runtime",
                                    "sha256": "0" * 64, "live_sources": ["nba_api"]},
                  as_of=AS_OF, source="silver:team_ratings:warehouse+nba_api"),
    )

    assert _answer_text(result).splitlines()[-1] == (
        "Some of these figures were refreshed from the NBA's live feed on "
        "2026-10-03; the rest came from the figures I had saved."
    )


def test_live_answer_without_a_date_names_the_source_and_claims_no_date() -> None:
    result = _result(_envelope(
        "live", identity={"kind": "live", "source": "nba_api"},
        as_of=None, source="silver:team_ratings:nba_api"))

    text = _answer_text(result)
    assert text.splitlines()[-1] == (
        "These figures came from the NBA's live feed, not from the figures I "
        "had saved, so they can differ from numbers you saw earlier."
    )
    assert "2026" not in text


def test_live_line_names_every_live_source_in_the_answer() -> None:
    result = _result(
        _envelope("a", identity={"kind": "live", "source": "nba_api"},
                  as_of=AS_OF, source="silver:team_ratings:nba_api"),
        _envelope("b", identity={"kind": "live", "source": "espn"},
                  as_of=AS_OF, source="silver:game_log:espn"),
    )

    assert "the NBA's live feed, ESPN" in _answer_text(result)


def test_gap_lines_still_render_next_to_the_live_source_line() -> None:
    from v2.contracts import Gap

    result = _result(_envelope(
        "live", identity={"kind": "live", "source": "nba_api"},
        as_of=AS_OF, source="silver:team_ratings:nba_api"))
    result.gaps = [Gap(kind="judge_unavailable", message="internal detail")]

    assert _answer_text(result).splitlines()[-1] == (
        "I couldn't double-check this answer, so treat the details with extra care."
    )


def test_unattributed_evidence_never_produces_a_live_label() -> None:
    result = _result(_envelope(
        "unknown", identity=None, as_of=None, source="silver:team_ratings:warehouse"))

    assert _answer_text(result).splitlines() == ["NET_RATING = 9.4 (net_rating)"]


def test_the_live_label_leaves_both_vintages_of_the_figures_untouched() -> None:
    live = _envelope("live", identity={"kind": "live", "source": "nba_api"},
                     as_of=AS_OF, source="silver:team_ratings:nba_api")
    stored = _envelope(
        "stored", identity={"kind": "warehouse", "warehouse_id": "configured-runtime",
                            "sha256": "0" * 64},
        as_of=WAREHOUSE_AS_OF, source="silver:team_ratings:warehouse")
    stored = stored.model_copy(update={
        "rows": [{"OFF_RATING": 118.2, "DEF_RATING": 108.8, "NET_RATING": 9.4}]})

    live_text = _answer_text(_result(live))
    stored_text = _answer_text(_result(stored))

    assert live.rows[0]["OFF_RATING"] == 119.5
    assert live.rows[0]["DEF_RATING"] == 110.1
    assert stored.rows[0]["OFF_RATING"] == 118.2
    assert stored.rows[0]["DEF_RATING"] == 108.8
    assert live_text.splitlines()[0] == stored_text.splitlines()[0]
    assert live_text.splitlines()[1:] == [LIVE_ONLY_LINE]
    assert stored_text.splitlines()[1:] == []


@pytest.mark.parametrize("identity", [
    {"kind": "live", "source": "nba_api"},
    {"kind": "live", "source": "basketball_reference"},
    {"kind": "live", "source": "espn"},
])
def test_every_live_source_has_plain_language_copy(identity: dict) -> None:
    result = _result(_envelope("live", identity=identity, as_of=AS_OF, source="x"))

    line = _answer_text(result).splitlines()[-1]
    assert line.startswith("These figures came from ")
    assert "2026-10-03" in line
    assert not any(token in line for token in ("nba_api", "basketball_reference", "espn"))


def test_the_published_table_keeps_stamping_the_live_date_for_each_figure() -> None:
    from decimal import Decimal

    from v2.api.routes import _public_evidence_tables

    envelope = _envelope(
        "live", identity={"kind": "live", "source": "nba_api"},
        as_of=AS_OF, source="silver:team_ratings:nba_api").model_copy(update={
            "rows": [{"NET_RATING": Decimal("9.4")}]})
    result = _result(envelope)
    result.execution = SimpleNamespace(evidence=[envelope])
    result.draft = SimpleNamespace(calculations=[])

    assert _public_evidence_tables(result) == [{
        "output_id": "NET_RATING",
        "subject_type": None,
        "subject_id": None,
        "value": "9.4",
        "unit": "net_rating",
        "provenance": {"capability": "team_ratings", "season": "2024-25",
                       "as_of": "2026-10-03"},
    }]