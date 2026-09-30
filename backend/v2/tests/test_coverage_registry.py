import os
import re

import pytest

import v2.adapters.coverage as coverage
from v2.adapters.coverage import (
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


def _stubbed_seasons(monkeypatch, mapping):
    monkeypatch.setattr(
        coverage,
        "table_seasons",
        lambda table: frozenset(mapping.get(str(table), ())),
    )


def test_generic_metric_uses_default_table():
    assert table_for_metric("POINTS") == "silver_boxscores"
    assert table_for_metric("plus-minus") == "silver_boxscores"


def test_known_metric_maps_to_its_table():
    assert table_for_metric("RAPTOR") == "silver_raptor_player"
    assert table_for_metric("RAPM-lite") == "silver_rapm"
    assert table_for_metric("true shooting") == "silver_advanced"


def test_covered_season_matches_warehouse_set(monkeypatch):
    _stubbed_seasons(monkeypatch, {"silver_boxscores": {"2025-26"}})
    verdict = coverage_check("points", "2025-26")
    assert verdict["covered"] is True
    assert verdict["table"] == "silver_boxscores"
    assert verdict["requested_season"] == "2025-26"
    assert verdict["available_seasons"] == ["2025-26"]
    _assert_plain_language(verdict["message"])


def test_uncovered_season_names_available_seasons(monkeypatch):
    _stubbed_seasons(monkeypatch, {"silver_boxscores": {"2025-26"}})
    verdict = coverage_check("points", "2012-13")
    assert verdict["covered"] is False
    assert verdict["table"] == "silver_boxscores"
    assert verdict["requested_season"] == "2012-13"
    assert verdict["available_seasons"] == ["2025-26"]
    assert "2025-26" in verdict["message"]
    assert "which season" in verdict["message"].casefold()
    _assert_plain_language(verdict["message"])


def test_unknown_table_has_empty_set(monkeypatch):
    _stubbed_seasons(monkeypatch, {})
    verdict = coverage_check("points", "2012-13", table="silver_future")
    assert verdict["covered"] is False
    assert verdict["available_seasons"] == []
    assert "which season" in verdict["message"].casefold()
    _assert_plain_language(verdict["message"])


def test_malformed_season_is_uncovered(monkeypatch):
    _stubbed_seasons(monkeypatch, {"silver_boxscores": {"2025-26"}})
    verdict = coverage_check("points", "banana")
    assert verdict["covered"] is False
    assert "which season" in verdict["message"].casefold()
    _assert_plain_language(verdict["message"])


def test_future_season_beyond_upper_bound_is_uncovered(monkeypatch):
    _stubbed_seasons(monkeypatch, {"silver_boxscores": {"2025-26"}})
    verdict = coverage_check("points", "2099-00")
    assert verdict["covered"] is False
    assert "which season" in verdict["message"].casefold()
    _assert_plain_language(verdict["message"])


def test_metric_coverage_rows_carry_verdicts(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_raptor_player": {"2025-26"},
    })
    result = metric_coverage(["POINTS", "RAPTOR"], season="2012-13")
    assert result["ok"] is True
    by_metric = {row["metric"]: row for row in result["rows"]}
    assert by_metric["POINTS"]["status"] == "unknown"
    assert by_metric["POINTS"]["covered"] is False
    assert by_metric["POINTS"]["available_seasons"] == ["2025-26"]
    assert by_metric["RAPTOR"]["status"] == "available"
    assert by_metric["RAPTOR"]["covered"] is False
    assert by_metric["RAPTOR"]["available_seasons"] == ["2025-26"]
    covered = metric_coverage(["POINTS"], season="2025-26")
    assert covered["rows"][0]["covered"] is True


def test_metric_coverage_without_season_has_no_verdicts():
    result = metric_coverage(["RAPTOR"])
    assert result["ok"] is True
    assert "covered" not in result["rows"][0]
    assert "available_seasons" not in result["rows"][0]
    assert result["rows"][0]["status"] == "available"


def test_advanced_gap_refuses_without_rewrite(monkeypatch):
    _stubbed_seasons(monkeypatch, {"silver_advanced": {"2025-26"}})
    task = _task(season="2023-24", metric_ids=("PIE",))
    result = ModelIntake._mark_uncovered_season(task)
    assert result.season.value == "2023-24"
    assert result.season.source == "user"
    assert result.season.confidence == 1.0
    assert result.open_questions != []
    assert any("silver_advanced" in item for item in result.open_questions)
    assert any("2023-24" in item for item in result.open_questions)
    assert result.assumptions != []
    for item in result.open_questions:
        _assert_plain_language(item)
    for item in result.assumptions:
        _assert_plain_language(item)
    verdict = coverage_check("PIE", "2023-24")
    assert verdict["covered"] is False
    trueshooting = _task(season="2023-24", metric_ids=("TRUESHOOTING",))
    refused = ModelIntake._mark_uncovered_season(trueshooting)
    assert refused.season.value == "2023-24"
    assert refused.open_questions != []


def test_old_boxscore_season_is_not_rewritten(monkeypatch):
    _stubbed_seasons(monkeypatch, {"silver_boxscores": {"2025-26"}})
    result = ModelIntake._mark_uncovered_season(_task())
    assert result.season.value == "2012-13"
    assert result.season.source == "user"
    assert result.open_questions != []
    assert any("2012-13" in item for item in result.open_questions)
    assert any("silver_boxscores" in item for item in result.open_questions)
    assert result.goal == "Compare scoring across seasons"


def test_absurd_future_season_is_rejected(monkeypatch):
    _stubbed_seasons(monkeypatch, {"silver_boxscores": {"2025-26"}})
    result = ModelIntake._mark_uncovered_season(_task(season="2099-00"))
    assert result.season.value == "2099-00"
    assert result.season.source == "user"
    assert result.open_questions != []
    assert any("2099-00" in item for item in result.open_questions)


def test_covered_season_is_left_alone(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2012-13", "2025-26"},
    })
    task = _task()
    assert ModelIntake._mark_uncovered_season(task) == task
    raptor = _task(season="2012-13", metric_ids=("RAPTOR",))
    _stubbed_seasons(monkeypatch, {
        "silver_raptor_player": {"2012-13", "2025-26"},
    })
    assert ModelIntake._mark_uncovered_season(raptor) == raptor


def test_empty_metrics_falls_back_to_default_table(monkeypatch):
    _stubbed_seasons(monkeypatch, {"silver_boxscores": {"2025-26"}})
    result = ModelIntake._mark_uncovered_season(
        _task(season="2023-24", metric_ids=()))
    assert result.season.value == "2023-24"
    assert result.open_questions != []
    assert any("silver_boxscores" in item for item in result.open_questions)


def test_missing_season_is_ignored():
    task = TaskSpec(goal="Compare scoring", mode="quick", deliverable="answer")
    assert ModelIntake._mark_uncovered_season(task) == task


def test_table_seasons_read_from_warehouse_file(tmp_path, monkeypatch):
    duckdb = pytest.importorskip("duckdb")
    path = tmp_path / "warehouse.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute(
        "CREATE TABLE silver_advanced (_season VARCHAR, value INTEGER)")
    connection.execute(
        "INSERT INTO silver_advanced VALUES ('2025-26', 1), ('2025-26', 2)")
    connection.execute("CREATE TABLE silver_shots (value INTEGER)")
    connection.execute("INSERT INTO silver_shots VALUES (1)")
    connection.close()
    monkeypatch.setattr(coverage, "warehouse_path", lambda: path)
    coverage.coverage_cache_clear()
    try:
        assert coverage.table_seasons("silver_advanced") == frozenset(
            {"2025-26"})
        assert coverage.table_seasons("silver_shots") == frozenset()
        assert coverage.table_seasons("silver_missing") == frozenset()
        assert coverage.max_known_season(["silver_advanced"]) == "2025-26"
        connection = duckdb.connect(str(path))
        connection.execute(
            "INSERT INTO silver_advanced VALUES ('2024-25', 3)")
        connection.close()
        stat = path.stat()
        os.utime(path, ns=(stat.st_mtime_ns + 2_000_000_000,
                           stat.st_mtime_ns + 2_000_000_000))
        assert coverage.table_seasons("silver_advanced") == frozenset(
            {"2025-26", "2024-25"})
    finally:
        coverage.coverage_cache_clear()


def test_missing_warehouse_file_degrades_to_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(
        coverage, "warehouse_path",
        lambda: tmp_path / "absent.duckdb")
    coverage.coverage_cache_clear()
    try:
        assert coverage.table_seasons("silver_boxscores") == frozenset()
        verdict = coverage.coverage_check("points", "2025-26")
        assert verdict["covered"] is False
        assert verdict["available_seasons"] == []
        refused = ModelIntake._mark_uncovered_season(
            _task(season="2025-26"))
        assert refused.season.value == "2025-26"
        assert refused.open_questions != []
    finally:
        coverage.coverage_cache_clear()
