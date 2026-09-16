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
    assert all({"OFF_RATING", "DEF_RATING", "NET_RATING"} <= row.keys()
               for row in result["rows"])
    envelope = call_capability(
        "playoff_team_ratings", {"season": "2025-26"})
    assert envelope.capability == "playoff_team_ratings"
    assert envelope.coverage == "Completed playoff games only."
