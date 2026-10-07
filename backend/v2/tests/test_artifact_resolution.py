from __future__ import annotations

import pytest
from v2.api.routes import _resolve_artifacts
from v2.contracts import (
    ArtifactIntent,
    ArtifactPoint,
    ArtifactSeries,
)

def _rows() -> list[dict]:
    return [
        {"output_id": "PTS", "display_name": "Points",
         "subject_display_name": "Shai Gilgeous-Alexander",
         "value": "30", "unit": "points per game"},
        {"output_id": "PTS", "display_name": "Points",
         "subject_display_name": "Luka Doncic",
         "value": "27", "unit": "points per game"},
    ]

def _intent(**overrides) -> ArtifactIntent:
    fields = {
        "id": "trend",
        "kind": "chart",
        "title": "Scoring trend",
        "series": [ArtifactSeries(name="Shai Gilgeous-Alexander", points=[
            ArtifactPoint(x="2025-01-01", output_id="PTS")])],
    }
    fields.update(overrides)
    return ArtifactIntent(**fields)

def test_a_point_resolves_to_the_published_number() -> None:
    resolved = _resolve_artifacts([_intent()], _rows())

    assert resolved[0]["series"] == [
        {"name": "Shai Gilgeous-Alexander", "values": [30.0]}]

def test_a_point_naming_no_published_row_is_dropped() -> None:
    resolved = _resolve_artifacts([_intent(series=[
        ArtifactSeries(name="Shai Gilgeous-Alexander", points=[
            ArtifactPoint(x="2025-01-01", output_id="PTS"),
            ArtifactPoint(x="2025-01-05", output_id="APG")])])], _rows())

    assert resolved[0]["series"][0]["values"] == [30.0]

def test_an_intent_whose_every_point_is_unpublished_is_not_published() -> None:
    resolved = _resolve_artifacts([_intent(series=[
        ArtifactSeries(name="Shai Gilgeous-Alexander", points=[
            ArtifactPoint(x="2025-01-01", output_id="APG")])])], _rows())

    assert resolved == []

def test_two_subjects_become_two_series() -> None:
    resolved = _resolve_artifacts([_intent(series=[
        ArtifactSeries(name="Shai Gilgeous-Alexander", points=[
            ArtifactPoint(x="2025-01-01", output_id="PTS")]),
        ArtifactSeries(name="Luka Doncic", points=[
            ArtifactPoint(x="2025-01-01", output_id="PTS")])])], _rows())

    assert [item["values"] for item in resolved[0]["series"]] == [
        [30.0], [27.0]]

def test_the_title_footnote_and_kind_survive_resolution() -> None:
    resolved = _resolve_artifacts(
        [_intent(footnote="points per game")], _rows())

    assert resolved[0]["kind"] == "chart"
    assert resolved[0]["title"] == "Scoring trend"
    assert resolved[0]["footnote"] == "points per game"

def test_a_non_numeric_published_value_is_dropped_not_rendered_as_zero() -> None:
    rows = [{"output_id": "PLAYER", "display_name": "Player",
             "subject_display_name": "SGA", "value": "Nikola Jokic",
             "unit": "unitless"}]
    resolved = _resolve_artifacts([_intent(series=[
        ArtifactSeries(name="Nikola Jokic", points=[
            ArtifactPoint(x="2025-01-01", output_id="PLAYER")])])], rows)

    assert resolved == []

def test_no_intents_publishes_nothing() -> None:
    assert _resolve_artifacts([], _rows()) == []