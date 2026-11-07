import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools import player


def _game(minutes=40, fg3m=0, fg3a=0, ftm=0, fta=0, pts=10):
    return {
        "MIN": minutes,
        "PTS": pts,
        "REB": 5,
        "AST": 5,
        "STL": 1,
        "BLK": 1,
        "TOV": 1,
        "FG3M": fg3m,
        "FG3A": fg3a,
        "FTM": ftm,
        "FTA": fta,
        "FG3_PCT": (fg3m / fg3a) if fg3a and fg3m is not None else None,
        "FT_PCT": (ftm / fta) if fta and ftm is not None else None,
    }


def test_unequal_attempts_use_total_makes_over_total_attempts():
    games = [_game(fg3m=1, fg3a=1, ftm=1, fta=1)]
    games += [_game(fg3m=0, fg3a=9, ftm=0, fta=9) for _ in range(9)]
    feats = player._gamelog_feats(games)
    assert feats is not None
    assert feats["FG3_PCT"] == 1 / 82
    assert feats["FT_PCT"] == 1 / 82
    assert feats["PTS36"] == 9.0


def test_makes_are_authoritative_not_rounded_pct_reconstruction():
    games = [_game(fg3m=1, fg3a=1, ftm=2, fta=3) for _ in range(10)]
    for game in games:
        game["FG3_PCT"] = 0.5
        game["FT_PCT"] = 0.5
    feats = player._gamelog_feats(games)
    assert feats["FG3_PCT"] == 1.0
    assert feats["FT_PCT"] == 2 / 3


def test_zero_attempts_return_none_not_zero():
    games = [_game(fg3m=0, fg3a=0, ftm=0, fta=0) for _ in range(10)]
    feats = player._gamelog_feats(games)
    assert feats is not None
    assert feats["FG3_PCT"] is None
    assert feats["FT_PCT"] is None


def test_missing_makes_or_attempts_pairs_are_excluded():
    games = [_game(fg3m=2, fg3a=4, ftm=1, fta=2) for _ in range(9)]
    missing_make = _game(fg3m=None, fg3a=100, ftm=100, fta=None)
    games.append(missing_make)
    feats = player._gamelog_feats(games)
    assert feats["FG3_PCT"] == 18 / 36
    assert feats["FT_PCT"] == 9 / 18


def test_constant_percentage_is_preserved():
    games = [_game(fg3m=2, fg3a=5, ftm=4, fta=5) for _ in range(10)]
    feats = player._gamelog_feats(games)
    assert feats["FG3_PCT"] == 0.4
    assert feats["FT_PCT"] == 0.8


def test_thresholds_ten_games_and_400_minutes():
    assert player._gamelog_feats(
        [_game(fg3m=1, fg3a=2) for _ in range(9)]) is None
    assert player._gamelog_feats(
        [_game(minutes=39, fg3m=1, fg3a=2) for _ in range(10)]) is None
    feats = player._gamelog_feats(
        [_game(minutes=40, fg3m=1, fg3a=2) for _ in range(10)])
    assert feats is not None
    assert feats["FG3_PCT"] == 0.5


def test_return_shape_and_no_input_mutation():
    games = [_game(fg3m=1, fg3a=2, ftm=1, fta=4) for _ in range(10)]
    before = copy.deepcopy(games)
    feats = player._gamelog_feats(games)
    assert games == before
    expected_keys = {feat for _, feat in player.BOX}
    expected_keys.update(player.PCTS)
    expected_keys.update(player.ADVS)
    assert set(feats) == expected_keys
    assert all(feats[feat] is None for feat in player.ADVS)


def test_pool_from_gamelogs_selects_makes_and_uses_them(monkeypatch):
    games = [_game(fg3m=1, fg3a=1, ftm=1, fta=1)]
    games += [_game(fg3m=0, fg3a=9, ftm=0, fta=9) for _ in range(9)]
    rows = [dict(game, _entity="player:123") for game in games]
    seen = {}

    def fake_read_df(sql, params, tries=5):
        seen["sql"] = sql
        seen["params"] = params
        return rows

    monkeypatch.setattr(player, "_read_df", fake_read_df)
    pool = player._pool_from_gamelogs("2025-26")

    assert "FG3M" in seen["sql"]
    assert "FTM" in seen["sql"]
    assert "FG3A" in seen["sql"]
    assert "FTA" in seen["sql"]
    assert seen["params"] == ["2025-26"]
    assert len(pool) == 1
    assert pool[0]["pid"] == 123
    assert pool[0]["feats"]["FG3_PCT"] == 1 / 82
    assert pool[0]["feats"]["FT_PCT"] == 1 / 82
