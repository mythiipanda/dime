import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources import nba_stats
from shared.tools import lineup_matrix as matrix_mod
from shared.tools._core import coerce_team_id
from shared.tools.lineup import get_lineup_stats

SEASON = "2015-16"
CLE_ID = coerce_team_id("CLE")
OTHER_ID = coerce_team_id("BOS")
CLE_STARTERS = "CLE starters A"
CLE_BENCH = "CLE bench B"
OTHER_UNIT = "OTHER team unit"


def _seed(dbpath):
    fetched = datetime.now(timezone.utc).isoformat()
    con = duckdb.connect(str(dbpath))
    try:
        con.execute(
            "CREATE TABLE silver_lineups ("
            "GROUP_ID VARCHAR, GROUP_NAME VARCHAR, TEAM_ID INTEGER, "
            "MIN DOUBLE, PTS DOUBLE, PLUS_MINUS DOUBLE, GP INTEGER, "
            "MEASURE VARCHAR, _source VARCHAR, _season VARCHAR, "
            "_fetched_at VARCHAR, _entity VARCHAR)"
        )
        con.execute(
            "CREATE TABLE silver_hist_possessions ("
            "game_id VARCHAR, possession_number INTEGER, "
            "offense_team_id INTEGER, defense_team_id INTEGER, "
            "points INTEGER, "
            "off_player_1 INTEGER, off_player_2 INTEGER, "
            "off_player_3 INTEGER, off_player_4 INTEGER, "
            "off_player_5 INTEGER, def_player_1 INTEGER, "
            "def_player_2 INTEGER, def_player_3 INTEGER, "
            "def_player_4 INTEGER, def_player_5 INTEGER, "
            "count_as_possession VARCHAR)"
        )
        rows = [
            ("101-102-103-104-105", CLE_STARTERS, CLE_ID, 120.0, 250.0,
             15.0, 40, "Total", "nba_api", SEASON, fetched,
             "lineups:2015-16"),
            ("101-102-103-104-105", CLE_STARTERS, CLE_ID, 12.0, 25.0,
             2.0, 1, "PerGame", "nba_api", SEASON, fetched,
             "lineups:2015-16"),
            ("201-202-203-204-205", CLE_BENCH, CLE_ID, 80.0, 170.0,
             -4.0, 25, "Total", "nba_api", SEASON, fetched,
             f"team:{CLE_ID}"),
            ("301-302-303-304-305", OTHER_UNIT, OTHER_ID, 200.0, 420.0,
             30.0, 60, "Total", "nba_api", SEASON, fetched,
             "lineups:2015-16"),
        ]
        con.executemany(
            "INSERT INTO silver_lineups VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        con.close()


def test_lineup_entity_tag_serves_backfill_rows(monkeypatch, tmp_path):
    dbpath = tmp_path / "scratch.duckdb"
    _seed(dbpath)
    monkeypatch.setattr(store, "DB_PATH", dbpath)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")

    def _no_live(*args, **kwargs):
        raise AssertionError("warehouse must serve static-season lineup rows")

    monkeypatch.setattr(nba_stats, "lineups", _no_live)
    res = get_lineup_stats.invoke({"team": "CLE", "season": SEASON})
    assert res["ok"] is True
    assert len(res["rows"]) > 0
    names = [r["GROUP_NAME"] for r in res["rows"]]
    assert OTHER_UNIT not in names
    assert set(names) <= {CLE_STARTERS, CLE_BENCH}
    assert names.count(CLE_STARTERS) == 1
    assert res["meta"]["rows_after_dedupe"] == 2
    got, _ = matrix_mod._lineup_names(CLE_ID, SEASON)
    assert len(got) == 2
