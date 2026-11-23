import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

import scripts.seed_early_team_seasons as seed


def test_seed_targets_hist_team_seasons() -> None:
    assert seed.TABLE == "silver_hist_team_seasons"


def test_league_slug_boundary() -> None:
    assert seed.league_slug(1948) == "BAA"
    assert seed.league_slug(1949) == "NBA"


def _wide(d: dict) -> pd.DataFrame:
    for i in range(25 - len(d)):
        d[f"pad{i}"] = [0] * len(next(iter(d.values())))
    return pd.DataFrame(d)


def test_per_game_tables_split() -> None:
    team_pg = _wide({"Team": ["A", "B"], "G": [80, 80],
                     "FG": [40.0, 38.0], "PTS": [110.0, 108.0]})
    opp_pg = _wide({"Team": ["A", "B"], "G": [80, 80],
                    "FG": [41.0, 39.0], "PTS": [111.0, 109.0]})
    totals = _wide({"Team": ["A", "B"], "G": [80, 80],
                    "FG": [3200, 3040], "PTS": [8800, 8640]})
    filler = pd.DataFrame({"x": [1]})
    out = seed.per_game_tables([filler, team_pg, opp_pg, totals])
    assert out["base"].iloc[0]["PTS"] == 110.0
    assert out["opponent"].iloc[0]["PTS"] == 111.0


def test_season_rows_map_and_ranks() -> None:
    standings = pd.DataFrame({
        "TeamID": [1, 2], "TeamCity": ["Boston", "Philadelphia"],
        "TeamName": ["Celtics", "Warriors"],
        "TeamSlug": ["celtics", "warriors"],
        "WINS": [60, 20], "LOSSES": [20, 60],
        "full": ["Boston Celtics", "Philadelphia Warriors"]})
    base = _wide({
        "Team": ["Boston Celtics", "Philadelphia Warriors"],
        "G": [80, 80], "FG": [40.0, 35.0], "FGA": [90.0, 95.0],
        "FG%": [0.444, 0.368], "FT": [20.0, 18.0], "FTA": [26.0, 24.0],
        "FT%": [0.769, 0.750], "ORB": [15.0, 12.0], "DRB": [40.0, 38.0],
        "TRB": [55.0, 50.0], "AST": [25.0, 20.0], "STL": [9.0, 8.0],
        "BLK": [6.0, 5.0], "TOV": [15.0, 17.0], "PF": [20.0, 22.0],
        "PTS": [110.0, 100.0]})
    opp = base.copy()
    opp["PTS"] = [100.0, 110.0]
    df = seed.season_rows(1961, standings, {"base": base, "opponent": opp})
    bos = df.filter((seed.pl.col("team_name") == "Boston Celtics")
                    & (seed.pl.col("measure_type") == "base"))
    assert bos["team_id"].to_list() == [1]
    assert bos["w"].to_list() == [60]
    assert bos["w_pct"].to_list() == [0.75]
    assert bos["plus_minus"].to_list() == [10.0]
    assert bos["w_rank"].to_list() == [1]
    opp_rows = df.filter(seed.pl.col("measure_type") == "opponent")
    assert opp_rows.height == 2


def test_alias_fallback_resolves_defunct_names() -> None:
    standings = pd.DataFrame({
        "TeamID": [42], "TeamCity": ["Ft. Wayne"],
        "TeamName": ["Zollner Pistons"], "TeamSlug": ["pistons"],
        "WINS": [30], "LOSSES": [40],
        "full": ["Ft. Wayne Zollner Pistons"]})
    base = _wide({
        "Team": ["Fort Wayne Pistons"], "G": [70],
        "FG": [35.0], "FGA": [90.0], "PTS": [105.0]})
    df = seed.season_rows(1955, standings, {"base": base})
    assert df["team_id"].to_list() == [42]
