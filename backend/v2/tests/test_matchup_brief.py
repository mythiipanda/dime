from unittest.mock import AsyncMock, patch
import pytest
from v2.adapters import call_capability
from v2.adapters.core import AdapterError


def _ratings_payload():
    return {
        "tool": "get_ratings",
        "ok": True,
        "rows": [
            {
                "TEAM_ID": 2,
                "TEAM_NAME": "Boston Celtics",
                "TEAM": "BOS",
                "GP": 82,
                "W": 58,
                "L": 24,
                "OFF_RATING": 119.8,
                "DEF_RATING": 110.2,
                "NET_RATING": 9.6,
                "PACE": 99.1,
            },
            {
                "TEAM_ID": 19,
                "TEAM_NAME": "New York Knicks",
                "TEAM": "NYK",
                "GP": 82,
                "W": 52,
                "L": 30,
                "OFF_RATING": 117.3,
                "DEF_RATING": 111.5,
                "NET_RATING": 5.8,
                "PACE": 98.4,
            },
        ],
        "meta": {"source": "warehouse", "season": "2025-26"},
    }


def _splits_payload(team):
    if team == "BOS":
        rows = [
            {"split": "home", "GP": 41, "W": 32, "L": 9, "PPG": 118.4},
            {"split": "away", "GP": 41, "W": 26, "L": 15, "PPG": 115.9},
            {"split": "last10", "GP": 10, "W": 7, "L": 3, "PPG": 117.2},
        ]
    else:
        rows = [
            {"split": "home", "GP": 41, "W": 30, "L": 11, "PPG": 116.1},
            {"split": "away", "GP": 41, "W": 22, "L": 19, "PPG": 114.3},
            {"split": "last10", "GP": 10, "W": 6, "L": 4, "PPG": 115.0},
        ]
    return {
        "tool": "get_team_splits",
        "ok": True,
        "rows": rows,
        "meta": {"source": "warehouse", "season": "2025-26", "team_id": 1},
    }


def _impact_payload(team):
    if team == "BOS":
        rows = {
            "team": "BOS",
            "out": [],
            "questionable": ["Sample Guard"],
            "availability_known": True,
            "net_rating": 9.6,
            "net_rank": 1,
            "last10": "7-3",
            "impact": "low",
        }
    else:
        rows = {
            "team": "NYK",
            "out": ["Sample Forward"],
            "questionable": [],
            "availability_known": True,
            "net_rating": 5.8,
            "net_rank": 3,
            "last10": "6-4",
            "impact": "moderate",
        }
    return {
        "tool": "get_injury_impact",
        "ok": True,
        "rows": rows,
        "meta": {"source": "warehouse", "season": "2025-26"},
    }


def _series_payload():
    return {
        "tool": "get_season_series",
        "ok": True,
        "rows": {
            "teams": ["BOS", "NYK"],
            "summary": {"games": 2, "bos_wins": 1, "nyk_wins": 1},
            "games": [
                {"game_id": "0022500001", "date": "Oct 22, 2025", "matchup": "BOS vs. NYK", "phase": "regular season", "winner": "BOS"},
                {"game_id": "0022500002", "date": "Jan 15, 2026", "matchup": "NYK vs. BOS", "phase": "regular season", "winner": "NYK"},
            ],
        },
        "meta": {"source": "warehouse", "season": "2025-26"},
    }


def _prediction_payload():
    return {
        "tool": "get_game_prediction",
        "ok": True,
        "matchup": {"home": "BOS", "away": "NYK"},
        "estimate": {
            "win_prob": {"BOS": 0.62, "NYK": 0.38},
            "projected_score": {"BOS": 116.4, "NYK": 112.8},
            "projected_total": 229.2,
        },
        "inputs": {"n_sims": 10000},
        "methodology": ["Monte Carlo"],
        "assumptions": [],
        "limitations": [],
        "meta": {"source": "warehouse", "season": "2025-26"},
    }


def _patched_call():
    ratings = _ratings_payload()
    series = _series_payload()
    prediction = _prediction_payload()

    def _splits_side_effect(args):
        return _splits_payload(args.get("team"))

    def _impact_side_effect(args):
        return _impact_payload(args.get("team"))

    return (
        patch("shared.tools.league.get_ratings", autospec=True),
        patch("shared.tools.team.get_team_splits", autospec=True),
        patch("shared.tools.team.get_injury_impact", autospec=True),
        patch("shared.tools.team.get_season_series", autospec=True),
        patch("shared.tools.prediction.get_game_prediction", autospec=True),
        ratings,
        series,
        prediction,
        _splits_side_effect,
        _impact_side_effect,
    )


def test_matchup_brief_composes_five_sections_from_fixtures():
    patches = _patched_call()
    pr, ps, pi, pe, pg, ratings, series, prediction, splits_fx, impact_fx = patches
    with pr as mr, ps as ms, pi as mi, pe as me, pg as mp:
        mr.ainvoke = AsyncMock(return_value=ratings)
        ms.ainvoke = AsyncMock(side_effect=lambda d: _splits_payload(d.get("team")))
        mi.ainvoke = AsyncMock(side_effect=lambda d: _impact_payload(d.get("team")))
        me.ainvoke = AsyncMock(return_value=series)
        mp.ainvoke = AsyncMock(return_value=prediction)
        env = call_capability("matchup_brief", {"a": "BOS", "b": "NYK", "season": "2025-26"})
    assert env.capability == "matchup_brief"
    assert env.season == "2025-26"
    assert env.rows["teams"] == ["BOS", "NYK"]
    assert env.rows["ratings"]["BOS"]["NET_RATING"] == 9.6
    assert env.rows["ratings"]["BOS"]["OFF_RATING"] == 119.8
    assert env.rows["ratings"]["BOS"]["DEF_RATING"] == 110.2
    assert env.rows["ratings"]["NYK"]["NET_RATING"] == 5.8
    assert env.rows["form"]["BOS"]["last10"] == "7-3"
    assert env.rows["form"]["NYK"]["last10"] == "6-4"
    assert env.rows["injuries"]["NYK"]["impact"] == "moderate"
    assert env.rows["injuries"]["BOS"]["impact"] == "low"
    assert env.rows["season_series"]["summary"]["games"] == 2
    assert len(env.rows["season_series"]["games"]) == 2
    assert env.rows["prediction"]["win_prob"]["BOS"] == 0.62
    assert env.rows["prediction"]["win_prob"]["NYK"] == 0.38
    assert env.qualification
    assert env.coverage


def test_matchup_brief_rejects_same_team():
    with pytest.raises(AdapterError):
        call_capability("matchup_brief", {"a": "BOS", "b": "BOS", "season": "2025-26"})


def test_matchup_brief_rejects_unknown_team():
    with pytest.raises(AdapterError):
        call_capability("matchup_brief", {"a": "BOS", "b": "ZZZ", "season": "2025-26"})
