
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools.team import get_team_game_log  # noqa: E402


def test_recent_games_have_scores_and_both_teams():
    out = get_team_game_log.invoke({"team": "Spurs", "limit": 5})
    assert out["ok"], out.get("error")
    games = out["games"]
    assert len(games) == 5
    for g in games:
        assert g["pts"] is not None and g["opp_pts"] is not None
        assert g["wl"] in ("W", "L")
        assert g["matchup"].startswith("SAS")
    assert "APR" in games[0]["date"]


def test_playoff_scope():
    out = get_team_game_log.invoke({"team": "NYK", "limit": 3,
                                    "playoffs": True})
    assert out["ok"], out.get("error")
    games = out["games"]
    assert len(games) == 3
    assert games[0]["date"] >= games[-1]["date"]


def test_bad_team_is_explicit_error():
    out = get_team_game_log.invoke({"team": "not a team", "limit": 5})
    assert out["ok"] is False
    assert out.get("error")
