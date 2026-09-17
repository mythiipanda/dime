from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import seed_2023_24_playoffs as seed
from app import store


def _hist_frame():
    return pl.DataFrame({
        "season_id": ["22023", "22023"], "team_id": [1, 2],
        "team_abbreviation": ["AAA", "BBB"], "team_name": ["A", "B"],
        "game_id": ["g1", "g1"], "game_date": ["2024-04-20"] * 2,
        "matchup": ["AAA vs. BBB", "BBB @ AAA"], "wl": ["W", "L"],
        "min": [240, 240], "pts": [100, 90], "fgm": [40, 35],
        "fga": [80, 80], "fg_pct": [.5, .438], "fg3m": [10, 8],
        "fg3a": [30, 28], "fg3_pct": [.333, .286], "ftm": [10, 12],
        "fta": [12, 15], "ft_pct": [.833, .8], "oreb": [8, 7],
        "dreb": [30, 28], "reb": [38, 35], "ast": [24, 20],
        "stl": [7, 5], "blk": [4, 3], "tov": [11, 13], "pf": [18, 20],
        "plus_minus": [10, -10], "season": [2024, 2024],
        "season_type": ["playoffs", "playoffs"],
    })


def _db(path: Path):
    con = duckdb.connect(str(path))
    con.register("rows", _hist_frame().to_arrow())
    con.execute("CREATE TABLE silver_hist_gamelogs AS SELECT * FROM rows")
    con.execute("CREATE TABLE silver_hist_player_seasons(player_id BIGINT, season INT)")
    con.execute("INSERT INTO silver_hist_player_seasons VALUES (10, 2024), (20, 2024)")
    con.close()


def test_team_seed_promotes_complete_paired_games_idempotently(tmp_path, monkeypatch):
    path = tmp_path / "warehouse.duckdb"
    _db(path)
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    assert seed.seed_team_rows() == 2
    assert seed.seed_team_rows() == 2
    con = duckdb.connect(str(path), read_only=True)
    try:
        assert con.execute(
            "SELECT _season, count(*) FROM silver_playoffs GROUP BY 1"
        ).fetchall() == [("2023-24", 2)]
    finally:
        con.close()


def test_team_seed_rejects_unpaired_game():
    frame = _hist_frame().head(1).select([
        pl.col(name.lower()).alias(name) for name in seed.TEAM_COLS
    ])
    with pytest.raises(ValueError, match="multiple teams|exactly two team rows"):
        seed.validate_team_rows(frame)


def test_player_population_is_historical_season_scoped(tmp_path):
    path = tmp_path / "warehouse.duckdb"
    _db(path)
    con = duckdb.connect(str(path), read_only=True)
    try:
        assert seed.player_ids(con) == [10, 20]
    finally:
        con.close()
