import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
import pytest

from shared import store

STATIC_PLAYERS = [
    {"id": 893, "full_name": "Michael Jordan"},
    {"id": 977, "full_name": "Kobe Bryant"},
]


def _seed(path):
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_raptor_player ("
            "PLAYER_ID VARCHAR, PLAYER_NAME VARCHAR, SEASON BIGINT, RAPTOR_TOTAL DOUBLE, "
            "WAR_TOTAL DOUBLE, MP DOUBLE, _season VARCHAR)"
        )
        con.executemany(
            "INSERT INTO silver_raptor_player VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("jordami01", "Michael Jordan", 1997, 8.4, 15.2, 3100.0, "1996-97"),
                ("bryanko01", "Kobe Bryant", 2009, 6.1, 11.4, 2900.0, "2008-09"),
                ("ackeral01", "Donald Ackerman", 1997, -3.0, 0.1, 40.0, "1996-97"),
            ],
        )
        con.execute(
            "CREATE TABLE silver_hist_player_seasons ("
            "player_id BIGINT, player_name VARCHAR, season BIGINT, age DOUBLE, team_abbreviation VARCHAR, "
            "gp BIGINT, min DOUBLE, pts DOUBLE, reb DOUBLE, ast DOUBLE, stl DOUBLE, blk DOUBLE, "
            "fg_pct DOUBLE, fg3_pct DOUBLE, ft_pct DOUBLE, ts_pct DOUBLE, efg_pct DOUBLE, usg_pct DOUBLE, "
            "off_rating DOUBLE, def_rating DOUBLE, net_rating DOUBLE)"
        )
        con.executemany(
            "INSERT INTO silver_hist_player_seasons VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (893, "Michael Jordan", 1997, 33, "CHI", 80, 31.9, 28.2, 6.5, 5.9, 2.0, 0.5, 0.49, 0.37, 0.83, 0.58, 0.53, 0.33, 115.0, 102.0, 13.0),
                (977, "Kobe Bryant", 2009, 30, "LAL", 82, 36.1, 26.8, 5.2, 4.9, 1.5, 0.4, 0.47, 0.35, 0.86, 0.56, 0.51, 0.32, 112.0, 105.0, 7.0),
            ],
        )
    finally:
        con.close()


@pytest.fixture()
def warehouse(tmp_path, monkeypatch):
    db = tmp_path / "compare-impact.duckdb"
    _seed(db)
    monkeypatch.setattr(store, "connect", lambda **_kw: duckdb.connect(str(db), read_only=True))
    return db


@pytest.fixture()
def static_names(monkeypatch):
    from nba_api.stats.static import players as static_players

    monkeypatch.setattr(static_players, "get_players", lambda: [dict(p) for p in STATIC_PLAYERS])


def test_compare_impact_historical_seasons_do_not_500(warehouse, static_names):
    from analyst.direct_data import product_compare

    result = product_compare.invoke({"players": "893:1996-97,977:2008-09", "season": "2025-26"})
    assert result.get("ok") is True, f"compare must not error on historical season specs: {result.get('error')}"
    jordan = next((p for p in result["players"] if p["player_id"] == 893), None)
    assert jordan is not None
    impact = jordan.get("impact") or {}
    assert impact.get("ok") is True, f"impact block should resolve by name, got {impact.get('error')}"
    assert impact.get("raptor_total") == pytest.approx(8.4)
    assert impact.get("rank") == 1


def test_compare_one_bad_block_degrades_honestly_not_500(warehouse, static_names):
    from analyst.direct_data import product_compare

    result = product_compare.invoke({"players": "893:1996-97,977:2008-09", "season": "2025-26"})
    assert result.get("ok") is True
    for player in result["players"]:
        for block in ("season_line", "impact", "zones", "contract", "arc"):
            assert block in player


def test_compare_season_line_hits_the_correct_end_year_row(warehouse, static_names):
    from analyst.direct_data import product_compare

    result = product_compare.invoke({"players": "893:1996-97,977:2008-09", "season": "2025-26"})
    jordan = next(p for p in result["players"] if p["player_id"] == 893)
    line = jordan.get("season_line") or {}
    assert line.get("ok") is True, f"season line must resolve at the end-year grain: {line.get('error')}"
    row = line.get("row") or {}
    assert row.get("ppg") == pytest.approx(28.2), "the labeled season must be the row actually rendered — mislabeled data is worse than empty"
