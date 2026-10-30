import v2.adapters.coverage as coverage
from v2.contracts import EvidenceRequirement, SeasonRef, TaskSpec


def test_matchup_brief_names_the_tables_its_sections_read():
    tables = coverage.declared_tables_for_capability("matchup_brief", {})
    assert "silver_team_ratings" in tables
    assert "silver_boxscores" in tables
    assert "silver_hist_gamelogs" in tables
    assert "silver_team_games" in tables
    assert "silver_playoffs" in tables
    assert "silver_playoff_gamelogs" in tables
    assert "silver_injuries" in tables
    assert "silver_scoreboard" in tables
