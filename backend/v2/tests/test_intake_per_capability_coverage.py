import v2.adapters.coverage as coverage
from v2.adapters.models import ModelIntake
from v2.contracts import EvidenceRequirement, SeasonRef, TaskSpec


def _stubbed_seasons(monkeypatch, mapping):
    monkeypatch.setattr(
        coverage,
        "table_seasons",
        lambda table: frozenset(mapping.get(str(table), ())),
    )


def _leaders_task(season="2024-25"):
    return TaskSpec(
        goal="Who led the league in assists",
        mode="quick",
        deliverable="answer",
        season=SeasonRef(value=season, source="user", confidence=1.0),
        required_evidence=["qualified_leaders"],
        requirements=[
            EvidenceRequirement(
                id="leaders",
                description="Assists leader",
                capability_options=["qualified_leaders"],
                capability_arguments={
                    "stat_category": "AST",
                    "season": season,
                },
            )
        ],
    )


def _ratings_task(season="2024-25"):
    return TaskSpec(
        goal="Team ratings",
        mode="quick",
        deliverable="answer",
        season=SeasonRef(value=season, source="user", confidence=1.0),
        required_evidence=["team_ratings"],
        requirements=[
            EvidenceRequirement(
                id="ratings",
                description="Team ratings",
                capability_options=["team_ratings"],
                capability_arguments={"season": season},
            )
        ],
    )


def test_assists_leader_resolves_from_leaders_table(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_leaders_ast": {"2024-25", "2025-26"},
        "silver_team_ratings": {"2025-26"},
    })
    assert ModelIntake._mark_uncovered_season(_leaders_task()) == _leaders_task()


def test_assists_leader_with_metric_id_resolves_from_leaders_table(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_leaders_ast": {"2024-25", "2025-26"},
        "silver_team_ratings": {"2025-26"},
    })
    task = _leaders_task().model_copy(update={"metric_ids": ["AST"]})
    assert ModelIntake._mark_uncovered_season(task) == task


def test_ratings_gap_names_ratings_table(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_leaders_ast": {"2024-25", "2025-26"},
        "silver_team_ratings": {"2025-26"},
    })
    result = ModelIntake._mark_uncovered_season(_ratings_task())
    assert result.open_questions != []
    assert any("silver_team_ratings" in item for item in result.open_questions)
    assert not any("silver_boxscores" in item for item in result.open_questions)
