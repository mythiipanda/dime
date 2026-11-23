import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

import scripts.seed_early_player_seasons as seed


def test_seed_targets_hist_player_seasons() -> None:
    assert seed.TABLE == "silver_hist_player_seasons"


def test_league_slug_covers_baa_years() -> None:
    assert seed.league_slug(1946) == "BAA"
    assert seed.league_slug(1947) == "BAA"
    assert seed.league_slug(1948) == "BAA"
    assert seed.league_slug(1949) == "NBA"
    assert seed.league_slug(1995) == "NBA"


def test_label_uses_start_year() -> None:
    assert seed.label(1946) == "1946-47"
    assert seed.label(1995) == "1995-96"


def _pg_frame() -> pd.DataFrame:
    return pd.DataFrame([
        {"Rk": 1, "Player": "Wilt Chamberlain", "Age": 25, "Team": "PHW",
         "Pos": "C", "G": 80, "MP": 48.5, "FG": 20.0, "FGA": 39.5,
         "FG%": 0.506, "FT": 10.4, "FTA": 17.0, "FT%": 0.613, "TRB": 25.7,
         "AST": 2.4, "PF": 1.5, "PTS": 50.4},
        {"Rk": 2, "Player": "Wilt Chamberlain", "Age": 25, "Team": "TOT",
         "Pos": "C", "G": 80, "MP": 48.5, "FG": 20.0, "FGA": 39.5,
         "FG%": 0.506, "FT": 10.4, "FTA": 17.0, "FT%": 0.613, "TRB": 25.7,
         "AST": 2.4, "PF": 1.5, "PTS": 50.4},
        {"Rk": 3, "Player": "Old Pro", "Age": 33, "Team": "MNL",
         "Pos": "F", "G": 66, "MP": 40.0, "FG": 6.0, "FGA": 15.0,
         "FG%": 0.4, "FT": 3.0, "FTA": 4.0, "FT%": 0.75, "TRB": 9.0,
         "AST": 3.0, "PF": 3.0, "PTS": 15.0},
    ])


def _adv_frame() -> pd.DataFrame:
    return pd.DataFrame([
        {"Rk": 1, "Player": "Wilt Chamberlain", "Age": 25, "Team": "PHW",
         "Pos": "C", "G": 80, "MP": 3880, "PER": 32.1, "TS%": 0.536,
         "FTr": 0.43, "OWS": 9.0, "DWS": 8.0, "WS": 17.0, "WS/48": 0.21},
    ])


def test_season_rows_maps_and_dedupes_tot() -> None:
    rows = seed.season_rows(1961, _pg_frame(), _adv_frame(),
                            {"Wilt Chamberlain": 76375})
    wilt = [r for r in rows if r["player_name"] == "Wilt Chamberlain"]
    assert len(wilt) == 1
    wilt = wilt[0]
    assert wilt["player_id"] == 76375
    assert wilt["team_abbreviation"] == "TOT"
    assert wilt["season"] == 1962
    assert wilt["gp"] == 80.0
    assert wilt["pts"] == 50.4
    assert wilt["ts_pct"] == 0.536
    assert wilt["efg_pct"] == 0.506
    old = [r for r in rows if r["player_name"] == "Old Pro"]
    assert old and old[0]["player_id"] is None


def test_season_rows_handles_missing_advanced() -> None:
    rows = seed.season_rows(1946, _pg_frame(), None, {})
    wilt = [r for r in rows if r["player_name"] == "Wilt Chamberlain"][0]
    assert wilt["ts_pct"] is None
    assert wilt["usg_pct"] is None
    assert wilt["pace"] is None
