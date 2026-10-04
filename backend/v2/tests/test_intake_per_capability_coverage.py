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


def _playoffs_task(season="2024-25"):
    return TaskSpec(
        goal="Playoff ratings",
        mode="quick",
        deliverable="answer",
        season=SeasonRef(value=season, source="user", confidence=1.0),
        required_evidence=["playoff_team_ratings"],
        requirements=[
            EvidenceRequirement(
                id="ratings",
                description="Playoff team ratings",
                capability_options=["playoff_team_ratings"],
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


def test_ratings_uncovered_season_admits_with_live_gap(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_leaders_ast": {"2024-25", "2025-26"},
        "silver_team_ratings": {"2025-26"},
    })
    result = ModelIntake._mark_uncovered_season(_ratings_task())
    assert result.season.value == "2024-25"
    assert result.open_questions == []
    assert any("silver_team_ratings" in item for item in result.assumptions)
    assert any("2024-25" in item for item in result.assumptions)


def test_capability_without_live_path_still_blocks_uncovered_season(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_playoffs": {"2025-26"},
    })
    result = ModelIntake._mark_uncovered_season(_playoffs_task())
    assert result.season.value == "2024-25"
    assert result.open_questions != []
    assert any("silver_playoffs" in item for item in result.open_questions)
    assert not any("silver_boxscores" in item for item in result.open_questions)


def _series_task(season="2024-25"):
    return TaskSpec(
        goal="Season series between two teams",
        mode="quick",
        deliverable="answer",
        season=SeasonRef(value=season, source="user", confidence=1.0),
        required_evidence=["season_series"],
        requirements=[
            EvidenceRequirement(
                id="series",
                description="Season series",
                capability_options=["season_series"],
                capability_arguments={"season": season},
            )
        ],
    )


def test_season_series_resolves_against_series_source_not_boxscores(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_team_games": set(),
        "silver_hist_gamelogs": {"2024-25", "2025-26"},
        "silver_playoffs": {"2024-25", "2025-26"},
        "silver_playoff_gamelogs": {"2024-25", "2025-26"},
    })
    assert coverage.tables_for_capability("season_series", {}) == (
        "silver_team_games", "silver_hist_gamelogs",
        "silver_playoffs", "silver_playoff_gamelogs")
    assert ModelIntake._mark_uncovered_season(_series_task()) == _series_task()


def test_season_series_still_blocks_season_missing_everywhere(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2024-25", "2025-26"},
        "silver_team_games": {"2025-26"},
        "silver_playoffs": {"2025-26"},
        "silver_playoff_gamelogs": {"2025-26"},
    })
    result = ModelIntake._mark_uncovered_season(_series_task())
    assert result.season.value == "2024-25"
    assert result.open_questions != []
    assert any("2024-25" in item for item in result.open_questions)
    assert not any("silver_boxscores" in item for item in result.open_questions)


def _comparison_task(season="2024-25", arguments=None):
    return TaskSpec(
        goal="Compare two players scoring",
        mode="quick",
        deliverable="answer",
        season=SeasonRef(value=season, source="user", confidence=1.0),
        required_evidence=["player_comparison"],
        requirements=[
            EvidenceRequirement(
                id="compare",
                description="Player scoring comparison",
                capability_options=["player_comparison"],
                capability_arguments={"season": season, **(arguments or {})},
            )
        ],
    )


def test_player_comparison_resolves_from_its_own_tables_not_boxscores(
    monkeypatch,
):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_player_gamelogs": {"2024-25", "2025-26"},
        "silver_on_off": {"2025-26"},
    })
    tables = coverage.tables_for_capability("player_comparison", {})
    assert tables[0] == "silver_player_gamelogs"
    assert "silver_on_off" in tables
    assert "silver_boxscores" not in tables
    assert (ModelIntake._mark_uncovered_season(_comparison_task())
            == _comparison_task())


def test_player_comparison_entry_ignores_a_stat_argument(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_player_gamelogs": {"2025-26"},
    })
    with_stat = coverage.tables_for_capability(
        "player_comparison", {"stat_category": "PTS"})
    assert with_stat == coverage.tables_for_capability(
        "player_comparison", {})
    result = ModelIntake._mark_uncovered_season(
        _comparison_task(arguments={"stat_category": "PTS"}))
    assert any("silver_player_gamelogs" in item for item in result.assumptions)
    assert not any("silver_leaders_pts" in item for item in result.assumptions)
    assert result.open_questions == []


def test_player_comparison_uncovered_season_admits_with_live_gap(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_player_gamelogs": {"2025-26"},
        "silver_on_off": {"2025-26"},
    })
    result = ModelIntake._mark_uncovered_season(_comparison_task())
    assert result.season.value == "2024-25"
    assert result.open_questions == []
    assert any("2024-25" in item for item in result.assumptions)
    assert any("player_comparison" in item for item in result.assumptions)


def _player_report_task(season="2024-25", arguments=None):
    return TaskSpec(
        goal="Jayson Tatum points per game in 2024-25",
        mode="quick",
        deliverable="answer",
        season=SeasonRef(value=season, source="user", confidence=1.0),
        required_evidence=["player_report"],
        requirements=[
            EvidenceRequirement(
                id="tatum_ppg",
                description="Single-player scoring average",
                capability_options=["player_report"],
                capability_arguments={"season": season, **(arguments or {})},
                metric_ids=["PTS", "PPG"],
                requested_outputs=["PPG"],
            )
        ],
    )


def test_player_report_resolves_from_its_own_tables_not_boxscores(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_player_season": set(),
        "silver_hist_player_seasons": {"2024-25", "2025-26"},
        "silver_advanced": {"2025-26"},
    })
    tables = coverage.tables_for_capability("player_report", {})
    assert tables[0] == "silver_player_season"
    assert "silver_hist_player_seasons" in tables
    assert "silver_advanced" in tables
    assert "silver_boxscores" not in tables
    assert (ModelIntake._mark_uncovered_season(_player_report_task())
            == _player_report_task())


def test_player_report_entry_ignores_a_stat_argument(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_player_season": set(),
        "silver_hist_player_seasons": {"2025-26"},
        "silver_advanced": {"2025-26"},
    })
    assert coverage.tables_for_capability(
        "player_report", {"stat_category": "PTS"}) == coverage.tables_for_capability(
        "player_report", {})
    result = ModelIntake._mark_uncovered_season(
        _player_report_task(arguments={"stat_category": "PTS"}))
    assert result.open_questions != []
    assert any("2024-25" in item for item in result.open_questions)
    assert not any("silver_leaders_pts" in item for item in result.open_questions)


def test_player_report_still_blocks_season_missing_everywhere(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2024-25", "2025-26"},
        "silver_player_season": set(),
        "silver_hist_player_seasons": {"2025-26"},
        "silver_advanced": {"2025-26"},
    })
    result = ModelIntake._mark_uncovered_season(_player_report_task())
    assert result.season.value == "2024-25"
    assert result.open_questions != []
    assert any("2024-25" in item for item in result.open_questions)
    assert not any("silver_boxscores" in item for item in result.open_questions)


def _brief_task(season="2024-25"):
    return TaskSpec(
        goal="Pre-game matchup brief for two teams",
        mode="quick",
        deliverable="answer",
        season=SeasonRef(value=season, source="user", confidence=1.0),
        required_evidence=["matchup_brief"],
        requirements=[
            EvidenceRequirement(
                id="brief",
                description="Matchup brief",
                capability_options=["matchup_brief"],
                capability_arguments={"season": season},
            )
        ],
    )


def test_matchup_brief_names_the_tables_its_sections_read():
    tables = coverage.tables_for_capability("matchup_brief", {})
    assert "silver_team_ratings" in tables
    assert "silver_boxscores" in tables
    assert "silver_hist_gamelogs" in tables
    assert "silver_team_games" in tables
    assert "silver_playoffs" in tables
    assert "silver_playoff_gamelogs" in tables
    assert "silver_injuries" in tables
    assert "silver_scoreboard" in tables


def test_matchup_brief_resolves_season_against_its_own_tables(monkeypatch):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_team_ratings": {"2025-26"},
        "silver_injuries": {"2025-26"},
        "silver_scoreboard": {"2025-26"},
        "silver_team_games": {"2025-26"},
        "silver_hist_gamelogs": {"2024-25", "2025-26"},
        "silver_playoffs": {"2024-25", "2025-26"},
        "silver_playoff_gamelogs": {"2024-25", "2025-26"},
    })
    assert ModelIntake._mark_uncovered_season(_brief_task()) == _brief_task()


def test_matchup_brief_still_blocks_season_missing_from_every_table(
    monkeypatch,
):
    _stubbed_seasons(monkeypatch, {
        "silver_boxscores": {"2025-26"},
        "silver_team_ratings": {"2025-26"},
        "silver_injuries": {"2025-26"},
        "silver_scoreboard": {"2025-26"},
        "silver_team_games": {"2025-26"},
        "silver_hist_gamelogs": {"2025-26"},
        "silver_playoffs": {"2025-26"},
        "silver_playoff_gamelogs": {"2025-26"},
    })
    result = ModelIntake._mark_uncovered_season(_brief_task())
    assert result.season.value == "2024-25"
    assert result.open_questions != []
    assert any("2024-25" in item for item in result.open_questions)
    assert any("silver_team_ratings" in item for item in result.open_questions)
