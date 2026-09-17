from app.tools.league import get_player_ratings, get_playoff_team_ratings
from v2.adapters import call_capability


def test_player_rating_boards_are_qualified_and_directional():
    offense = get_player_ratings.invoke({
        "season": "2025-26", "metric": "offense", "limit": 5,
        "min_minutes": 1000,
    })
    defense = get_player_ratings.invoke({
        "season": "2025-26", "metric": "defense", "limit": 5,
        "min_minutes": 1000,
    })
    assert offense["ok"] and defense["ok"]
    assert offense["rows"] == sorted(
        offense["rows"], key=lambda row: row["OFF_RATING"], reverse=True)
    assert defense["rows"] == sorted(
        defense["rows"], key=lambda row: row["DEF_RATING"])
    assert all(row["MINUTES"] >= 1000 for row in offense["rows"] + defense["rows"])


def test_playoff_team_ratings_are_real_rating_evidence():
    result = get_playoff_team_ratings.invoke({"season": "2025-26"})
    assert result["ok"] and result["rows"]
    assert result["meta"]["as_of"]
    assert result["meta"]["method"] == "NBA box-score estimated possessions"
    assert all({"OFF_RATING", "DEF_RATING", "NET_RATING"} <= row.keys()
               for row in result["rows"])
    envelope = call_capability(
        "playoff_team_ratings", {"season": "2025-26"})
    assert envelope.capability == "playoff_team_ratings"
    assert envelope.coverage == "Completed playoff games only."


def test_every_rating_board_declares_rank_scope() -> None:
    for name, arguments in (
        ("team_ratings", {"season": "2025-26"}),
        ("player_ratings", {"season": "2025-26", "metric": "offense"}),
        ("player_ratings", {"season": "2025-26", "metric": "defense"}),
        ("playoff_team_ratings", {"season": "2025-26"}),
    ):
        envelope = call_capability(name, arguments)
        assert envelope.rows
        assert envelope.qualification
        assert envelope.coverage


def test_rest_splits_expose_all_three_buckets_with_samples():
    from v2.adapters import call_capability
    result = call_capability("rest_splits", {"team_abbrev": "DEN", "season": "2025-26"})
    buckets = result.rows["rest_buckets"]
    assert set(buckets) == {"zero_days", "one_day", "two_plus_days"}
    for values in buckets.values():
        assert values["games"] == values["wins"] + values["losses"]
        assert values["win_pct"] is None or 0 <= values["win_pct"] <= 1


def test_rookie_capability_declares_first_season_qualification():
    from v2.adapters import CAPABILITIES
    assert "no player row in any prior" in CAPABILITIES["rookie_leaders"].qualification


def test_warehouse_freshness_declares_authoritative_source_and_generation_time():
    from app.tools.league import get_warehouse_freshness
    result = get_warehouse_freshness.invoke({})
    assert result["ok"] is True
    assert result["meta"]["source"] == "warehouse"
    assert result["meta"]["generated_at"]
    assert all({"table", "rows", "last_fetch", "age_hours", "expected", "stale"}
               <= set(row) for row in result["rows"])

def test_team_ratings_exposes_rankable_ts_and_turnover_metrics():
    from v2.adapters.capabilities import CAPABILITIES, CAPABILITY_DESCRIPTIONS
    spec = CAPABILITIES["team_ratings"]
    assert spec.units["TS_PCT"] == "percent_0_100"
    assert spec.units["TM_TOV_PCT"] == "percent_0_100"
    description = CAPABILITY_DESCRIPTIONS["team_ratings"]
    assert "lower is better for DEF_RATING and TM_TOV_PCT" in description
