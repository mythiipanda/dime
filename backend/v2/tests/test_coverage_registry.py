import re

from v2.adapters.coverage import (
    COVERAGE_REGISTRY,
    DEFAULT_SEASON,
    coverage_check,
    metric_coverage,
    table_for_metric,
)
from v2.adapters.models import ModelIntake
from v2.contracts import SeasonRef, TaskSpec


INFRA_WORDS = ("sync", "pipeline", "endpoint", "cache", "warehouse", "tool")


def _word_present(text, word):
    return re.search(r"\b" + re.escape(word) + r"\b", text.casefold()) is not None


def _assert_plain_language(text):
    for word in INFRA_WORDS:
        assert not _word_present(text, word)


def _task(season="2012-13", metric_ids=("POINTS",)):
    return TaskSpec(
        goal="Compare scoring across seasons",
        mode="quick",
        deliverable="answer",
        metric_ids=list(metric_ids),
        season=SeasonRef(value=season, source="user", confidence=1.0),
    )


def test_default_floor_is_2015_16():
    assert DEFAULT_SEASON == "2015-16"
    assert COVERAGE_REGISTRY["silver_boxscores"] == "2015-16"
    assert COVERAGE_REGISTRY["silver_boxscores_ext"] == "2015-16"
    assert COVERAGE_REGISTRY["silver_lineups"] == "2015-16"


def test_generic_metric_uses_default_table():
    assert table_for_metric("POINTS") == "silver_boxscores"
    assert table_for_metric("plus-minus") == "silver_boxscores"


def test_known_metric_maps_to_its_table():
    assert table_for_metric("RAPTOR") == "silver_raptor_player"
    assert table_for_metric("RAPM-lite") == "silver_rapm"
    assert table_for_metric("true shooting") == "silver_advanced"


def test_raptor_exception_floor():
    assert COVERAGE_REGISTRY["silver_raptor_player"] == "1976-77"
    assert COVERAGE_REGISTRY["silver_raptor_team"] == "2013-14"
    verdict = coverage_check("RAPTOR", "1970-71")
    assert verdict["covered"] is False
    assert verdict["earliest_season"] == "1976-77"
    assert "1976-77" in verdict["message"]
    _assert_plain_language(verdict["message"])


def test_out_of_coverage_verdict_names_earliest_season():
    verdict = coverage_check("points", "2012-13")
    assert verdict["covered"] is False
    assert verdict["table"] == "silver_boxscores"
    assert verdict["requested_season"] == "2012-13"
    assert verdict["earliest_season"] == "2015-16"
    assert "2015-16" in verdict["message"]
    _assert_plain_language(verdict["message"])


def test_in_coverage_verdict():
    verdict = coverage_check("points", "2015-16")
    assert verdict["covered"] is True
    assert verdict["earliest_season"] == "2015-16"
    _assert_plain_language(verdict["message"])
    verdict = coverage_check("RAPTOR", "2012-13")
    assert verdict["covered"] is True
    assert verdict["earliest_season"] == "1976-77"


def test_unknown_table_defaults_to_floor():
    verdict = coverage_check("points", "2012-13", table="silver_future")
    assert verdict["earliest_season"] == "2015-16"
    assert verdict["covered"] is False
    assert "2015-16" in verdict["message"]


def test_metric_coverage_rows_carry_verdicts():
    result = metric_coverage(["POINTS", "RAPTOR"], season="2012-13")
    assert result["ok"] is True
    by_metric = {row["metric"]: row for row in result["rows"]}
    assert by_metric["POINTS"]["status"] == "unknown"
    assert by_metric["POINTS"]["covered"] is False
    assert by_metric["POINTS"]["earliest_season"] == "2015-16"
    assert by_metric["RAPTOR"]["status"] == "available"
    assert by_metric["RAPTOR"]["covered"] is True
    assert by_metric["RAPTOR"]["earliest_season"] == "1976-77"


def test_metric_coverage_without_season_has_no_verdicts():
    result = metric_coverage(["RAPTOR"])
    assert result["ok"] is True
    assert "covered" not in result["rows"][0]
    assert "earliest_season" not in result["rows"][0]
    assert result["rows"][0]["status"] == "available"


def test_intake_floor_helper_floors_old_season():
    floored = ModelIntake._floor_season_for_coverage(_task())
    assert floored.season.value == "2015-16"
    assert floored.season.source == "resolved"
    assert floored.season.confidence == 1.0
    assert any("2015-16" in note for note in floored.assumptions)
    for note in floored.assumptions:
        _assert_plain_language(note)
    assert floored.open_questions == []
    assert floored.goal == "Compare scoring across seasons"


def test_intake_floor_helper_leaves_covered_season_alone():
    task = _task(season="2015-16")
    assert ModelIntake._floor_season_for_coverage(task) == task
    raptor = _task(season="2012-13", metric_ids=("RAPTOR",))
    assert ModelIntake._floor_season_for_coverage(raptor) == raptor


def test_intake_floor_helper_defaults_empty_metrics():
    floored = ModelIntake._floor_season_for_coverage(_task(metric_ids=()))
    assert floored.season.value == "2015-16"
    assert any("2015-16" in note for note in floored.assumptions)
    assert floored.open_questions == []


def test_intake_floor_helper_ignores_missing_season():
    task = TaskSpec(goal="Compare scoring", mode="quick", deliverable="answer")
    assert ModelIntake._floor_season_for_coverage(task) == task
