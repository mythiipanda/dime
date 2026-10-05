import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb

from shared import store


PID = 2544
NAME = "LeBron James"


def _seed(path):
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_hist_player_seasons ("
            "player_id BIGINT, player_name VARCHAR, team_abbreviation VARCHAR, "
            "season INTEGER, age DOUBLE, gp BIGINT, min DOUBLE, pts DOUBLE, "
            "reb DOUBLE, ast DOUBLE, stl DOUBLE, blk DOUBLE, tov DOUBLE, "
            "fgm DOUBLE, fga DOUBLE, fg_pct DOUBLE, fg3m DOUBLE, fg3a DOUBLE, "
            "fg3_pct DOUBLE, ftm DOUBLE, fta DOUBLE, ft_pct DOUBLE, "
            "ts_pct DOUBLE)"
        )
        con.execute(
            "INSERT INTO silver_hist_player_seasons VALUES "
            "(2544, 'LeBron James', 'LAL', 2024, 39, 71, 35.3, 25.7, 7.3, 8.3, "
            "1.3, 0.5, 3.5, 9.6, 17.8, 0.54, 2.1, 5.1, 0.41, 4.3, 5.7, 0.75, 0.63), "
            "(2544, 'LeBron James', 'LAL', 2025, 40, 70, 34.9, 24.4, 7.8, 8.2, "
            "1.0, 0.6, 3.4, 9.2, 17.9, 0.51, 2.2, 5.7, 0.38, 3.8, 4.9, 0.78, 0.60)"
        )
        con.execute(
            "CREATE TABLE silver_leaders_pts ("
            "PLAYER_ID BIGINT, PLAYER VARCHAR, TEAM VARCHAR, GP BIGINT, "
            "MIN BIGINT, PTS BIGINT, REB BIGINT, AST BIGINT, STL BIGINT, "
            "BLK BIGINT, FGM BIGINT, FGA BIGINT, FG_PCT DOUBLE, "
            "FG3M BIGINT, FG3A BIGINT, FG3_PCT DOUBLE, "
            "FTM BIGINT, FTA BIGINT, FT_PCT DOUBLE, _season VARCHAR)"
        )
        con.execute(
            "INSERT INTO silver_leaders_pts VALUES "
            "(2544, 'LeBron James', 'LAL', 60, 1989, 1500, 420, 480, 60, 30, "
            "560, 1100, 0.509, 120, 300, 0.40, 260, 340, 0.765, '2025-26')"
        )
        con.execute(
            "CREATE TABLE silver_player_season ("
            "PLAYER_ID BIGINT, PLAYER VARCHAR, TEAM VARCHAR, AGE DOUBLE, "
            "GP BIGINT, MPG DOUBLE, PPG DOUBLE, RPG DOUBLE, APG DOUBLE, "
            "SPG DOUBLE, BPG DOUBLE, FG_PCT DOUBLE, FG3_PCT DOUBLE, "
            "FT_PCT DOUBLE, _season VARCHAR)"
        )
        con.execute(
            "INSERT INTO silver_player_season VALUES "
            "(2544, 'LeBron James', 'LAL', 40.0, 60, 33.1, 25.0, 6.1, 7.2, "
            "1.2, 0.6, 0.515, 0.317, 0.737, '2025-26')"
        )
        con.execute(
            "CREATE TABLE silver_advanced ("
            "PLAYER_ID BIGINT, TS_PCT DOUBLE, _season VARCHAR)"
        )
        con.execute(
            "INSERT INTO silver_advanced VALUES (2544, 0.61, '2025-26')"
        )
        con.execute(
            "CREATE TABLE silver_raptor_player ("
            "PLAYER_NAME VARCHAR, SEASON BIGINT, RAPTOR_TOTAL DOUBLE, "
            "_season VARCHAR)"
        )
        con.execute(
            "INSERT INTO silver_raptor_player VALUES "
            "('LeBron James', 2024, 3.5, '2023-24'), "
            "('LeBron James', 2022, 4.7, '2021-22')"
        )
    finally:
        con.close()


def _warehouse(monkeypatch, tmp_path):
    path = tmp_path / "arc.duckdb"
    _seed(path)
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    return path


def test_arc_reads_as_one_series_with_honest_gaps(monkeypatch, tmp_path):
    _warehouse(monkeypatch, tmp_path)
    from shared.tools import career_arc as arc

    rows = arc.arc_for_id(PID)
    by_year = {r["end_year"]: r for r in rows}
    assert sorted(by_year) == [2024, 2025, 2026]
    assert by_year[2024]["pts"] == 25.7
    assert by_year[2024]["raptor"] == 3.5
    assert by_year[2024]["raptor_gap"] is False
    assert by_year[2025]["pts"] == 24.4
    assert by_year[2025]["raptor"] is None
    assert by_year[2025]["raptor_gap"] is True
    assert by_year[2026]["pts"] == 25.0
    assert by_year[2026]["raptor"] is None
    assert by_year[2026]["raptor_gap"] is True
    assert by_year[2026]["source"] == "current"
    assert by_year[2024]["season"] == "2023-24"


def test_arc_never_fabricates_missing_seasons(monkeypatch, tmp_path):
    _warehouse(monkeypatch, tmp_path)
    from shared.tools import career_arc as arc

    rows = arc.arc_for_id(999999)
    assert rows == []


def test_season_line_covers_current_season(monkeypatch, tmp_path):
    _warehouse(monkeypatch, tmp_path)
    from shared.tools import player as pm

    out = pm.get_season_averages.invoke(
        {"player_id": str(PID), "season": "2025-26"})
    assert out.get("ok") is True
    line = out["rows"][0]
    assert line["PPG"] == 25.0
    assert line["GP"] == 60


def test_history_covers_current_season(monkeypatch, tmp_path):
    _warehouse(monkeypatch, tmp_path)
    from shared.tools.history import get_historical_leaders

    res = get_historical_leaders.invoke({
        "category": "pts", "start_season": 2025,
        "end_season": 2026, "limit": 5, "mode": "leaders",
    })
    assert res["ok"] is True
    seasons = [s["season"] for s in res["rows"]["seasons"]]
    assert 2026 in seasons
    assert res["meta"]["end_season"] == 2026


def test_compare_metrics_flags_raptor_gap(monkeypatch, tmp_path):
    _warehouse(monkeypatch, tmp_path)
    from shared.tools import player as pm

    out = pm.compare_metrics.invoke(
        {"a": str(PID), "b": str(PID), "season": "2025-26"})
    assert out.get("ok") is True
    assert out["meta"].get("raptor_gap") is True
