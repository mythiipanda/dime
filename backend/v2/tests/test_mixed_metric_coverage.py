import v2.adapters.coverage as coverage
from v2.adapters.models import ModelIntake
from v2.contracts import SeasonRef, TaskSpec


def _task(season, metric_ids):
    return TaskSpec(
        goal="Compare scoring and impact",
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


def test_mixed_metrics_flagged_when_one_table_lacks_season(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_raptor_player": {"2012-13"},
    })
    result = ModelIntake._mark_uncovered_season(
        _task("2025-26", ("POINTS", "RAPTOR")))
    assert result.season.value == "2025-26"
    assert result.open_questions != []
    assert any("2025-26" in item for item in result.open_questions)
    assert any("silver_raptor_player" in item for item in result.open_questions)


def test_mixed_metrics_left_alone_when_all_tables_cover_season(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_raptor_player": {"2025-26"},
    })
    task = _task("2025-26", ("POINTS", "RAPTOR"))
    assert ModelIntake._mark_uncovered_season(task) == task


def test_single_metric_still_flags_its_own_missing_table(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_raptor_player": {"2012-13"},
    })
    result = ModelIntake._mark_uncovered_season(_task("2025-26", ("RAPTOR",)))
    assert result.open_questions != []
    assert any("silver_raptor_player" in item for item in result.open_questions)
