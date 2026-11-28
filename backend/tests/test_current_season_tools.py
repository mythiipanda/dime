import datetime
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


def test_current_season_tracks_the_calendar():
    from shared.tools._core import current_season

    assert current_season(datetime.date(2026, 11, 19)) == "2026-27"
    assert current_season(datetime.date(2027, 1, 15)) == "2026-27"
    assert current_season(datetime.date(2027, 6, 30)) == "2026-27"
    assert current_season(datetime.date(2026, 7, 1)) == "2026-27"
    assert current_season(datetime.date(2026, 10, 1)) == "2026-27"
    assert current_season(datetime.date(2027, 10, 1)) == "2027-28"


def test_trade_check_defaults_to_the_current_season(monkeypatch, tmp_path):
    import duckdb

    from shared import store
    from shared.tools import get_trade_check

    path = tmp_path / "trade.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, "
        "SALARY_2025_26 INTEGER, SALARY_2026_27 INTEGER, _season VARCHAR, "
        "_fetched_at VARCHAR)")
    con.execute(
        "INSERT INTO silver_salaries VALUES "
        "('LeBron James', 'LAL', 50000000, 51000000, '2026-27', NULL), "
        "('Giannis Antetokounmpo', 'MIA', 40000000, 41000000, '2026-27', NULL)")
    from cap_line_fixtures import seed_cap_history
    seed_cap_history(con)
    con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()

    import shared.tools.league as league_mod
    monkeypatch.setattr(league_mod, "current_season",
                        lambda today=None: "2026-27")
    out = get_trade_check.invoke({
        "team_a": "LAL", "players_a": "LeBron James",
        "team_b": "MIA", "players_b": "Giannis Antetokounmpo"})
    assert out["ok"] is True
    assert out["meta"]["season"] == "2026-27"

    hist = get_trade_check.invoke({
        "team_a": "LAL", "players_a": "LeBron James",
        "team_b": "MIA", "players_b": "Giannis Antetokounmpo",
        "season": "2025-26"})
    assert hist["ok"] is True
    assert hist["meta"]["season"] == "2025-26"


def test_trade_guard_names_the_season_on_a_stale_team_premise(
        monkeypatch, tmp_path):
    import duckdb

    from shared import store
    from shared.tools import get_trade_check

    path = tmp_path / "stale.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, "
        "SALARY_2025_26 INTEGER, SALARY_2026_27 INTEGER, _season VARCHAR, "
        "_fetched_at VARCHAR)")
    con.execute(
        "INSERT INTO silver_salaries VALUES "
        "('Jaylen Brown', 'PHI', 57000000, 58000000, '2026-27', NULL), "
        "('Jayson Tatum', 'BOS', 58000000, 59000000, '2026-27', NULL)")
    con.execute(
        "CREATE TABLE silver_leaders_pts (PLAYER VARCHAR, TEAM VARCHAR, "
        "GP INTEGER, PTS REAL, REB REAL, AST REAL, STL REAL, BLK REAL, "
        "TOV REAL, PLAYER_ID INTEGER, _season VARCHAR, _fetched_at VARCHAR)")
    con.execute(
        "INSERT INTO silver_leaders_pts VALUES "
        "('Jaylen Brown', 'BOS', 70, 25.0, 6.0, 3.0, 1.5, 0.5, 3.0, 1, "
        "'2025-26', NULL), "
        "('Jayson Tatum', 'BOS', 70, 26.0, 8.0, 6.0, 1.0, 0.5, 2.5, 2, "
        "'2025-26', NULL)")
    from cap_line_fixtures import seed_cap_history
    seed_cap_history(con)
    con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()

    current = get_trade_check.invoke({
        "season": "2026-27", "team_a": "BOS", "players_a": "Jaylen Brown",
        "team_b": "LAL", "players_b": "LeBron James"})
    assert current["ok"] is False
    assert "Jaylen Brown" in current["error"]
    assert "PHI" in current["error"] and "2026-27" in current["error"]

    past = get_trade_check.invoke({
        "season": "2025-26", "team_a": "BOS", "players_a": "Jaylen Brown",
        "team_b": "LAL", "players_b": "LeBron James"})
    assert "salary data lists Jaylen Brown" not in str(past.get("error", ""))


def test_contract_value_falls_back_to_latest_production_season(
        monkeypatch, tmp_path):
    import duckdb

    from shared import store
    from shared.tools import get_contract_value

    path = tmp_path / "contracts.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE silver_leaders_pts (PLAYER VARCHAR, TEAM VARCHAR, "
        "GP INTEGER, PTS REAL, REB REAL, AST REAL, STL REAL, BLK REAL, "
        "TOV REAL, PLAYER_ID INTEGER, _season VARCHAR, _fetched_at VARCHAR)")
    con.execute(
        "INSERT INTO silver_leaders_pts VALUES "
        "('Test Star One', 'BOS', 70, 25.0, 6.0, 3.0, 1.5, 0.5, 3.0, 1, "
        "'2025-26', NULL), "
        "('Test Star Two', 'LAL', 70, 12.0, 4.0, 2.0, 0.5, 0.5, 2.0, 2, "
        "'2025-26', NULL), "
        "('Test Star Three', 'MIA', 70, 18.0, 7.0, 5.0, 1.0, 0.5, 2.5, 3, "
        "'2025-26', NULL), "
        "('Test Star Four', 'NYK', 70, 9.0, 3.0, 1.0, 0.5, 0.2, 1.5, 4, "
        "'2025-26', NULL)")
    con.execute(
        "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, "
        "SALARY_2025_26 INTEGER, _season VARCHAR, _fetched_at VARCHAR)")
    con.execute(
        "INSERT INTO silver_salaries VALUES "
        "('Test Star One', 'PHI', 50000000, '2026-27', NULL), "
        "('Test Star Two', 'LAL', 10000000, '2026-27', NULL), "
        "('Test Star Three', 'MIA', 30000000, '2026-27', NULL), "
        "('Test Star Four', 'NYK', 5000000, '2026-27', NULL)")
    con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()

    out = get_contract_value.invoke({"season": "2026-27",
                                     "player": "Test Star One"})
    assert out["ok"] is True
    meta = out["meta"]
    assert meta["production_season"] == "2025-26"
    assert meta["salary_season"] == "2026-27"
    assert meta["requested_season"] == "2026-27"
    assert meta["production_fallback"] == "2025-26"

    direct = get_contract_value.invoke({"season": "2025-26",
                                        "player": "Test Star One"})
    assert direct["ok"] is True
    assert "production_fallback" not in direct["meta"]


def test_four_factors_falls_back_to_latest_season_with_rows(
        monkeypatch, tmp_path):
    import duckdb

    from shared import store
    from shared.tools import get_team_four_factors

    path = tmp_path / "four.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE silver_team_games (Team_ID INTEGER, Game_ID VARCHAR, "
        "_season VARCHAR, FGM INTEGER, FG3M INTEGER, FGA INTEGER, "
        "FTA INTEGER, TOV INTEGER, OREB INTEGER, DREB INTEGER, "
        "MIN INTEGER, PTS INTEGER, WL VARCHAR, MATCHUP VARCHAR)")
    rows = []
    for gid in ("0022500001", "0022500002"):
        rows += [
            (1, gid, "2025-26", 40, 12, 85, 20, 12, 10, 30, 4800, 110, "W",
             "BOS vs. MIA"),
            (2, gid, "2025-26", 35, 10, 80, 18, 14, 11, 28, 4700, 95, "L",
             "MIA @ BOS"),
        ]
    con.executemany("INSERT INTO silver_team_games VALUES "
                    "(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()

    out = get_team_four_factors.invoke({"season": "2026-27", "team": "BOS"})
    assert out["ok"] is True
    assert out["meta"]["season"] == "2025-26"
    assert out["meta"]["requested_season"] == "2026-27"
    assert out["meta"]["season_fallback"] == "2025-26"
    assert [r["TEAM"] for r in out["rows"]] == ["BOS"]

    direct = get_team_four_factors.invoke({"season": "2025-26"})
    assert direct["ok"] is True
    assert "season_fallback" not in direct["meta"]


def test_season_player_team_ignores_tot_aggregates(monkeypatch, tmp_path):
    import duckdb

    from shared import store
    from shared.tools.league.cba_cap import _season_player_team

    path = tmp_path / "tot.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE silver_leaders_pts (PLAYER VARCHAR, TEAM VARCHAR, "
        "GP INTEGER, PTS REAL, _season VARCHAR, _fetched_at VARCHAR)")
    con.execute(
        "INSERT INTO silver_leaders_pts VALUES "
        "('Jaylen Brown', 'TOT', 70, 25.0, '2025-26', NULL), "
        "('Jayson Tatum', 'BOS', 70, 26.0, '2025-26', NULL)")
    con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()

    lookup = store.connect(read_only=True)
    try:
        assert _season_player_team(
            lookup, "Jaylen Brown", "2025-26", None) is None
        assert _season_player_team(
            lookup, "Jayson Tatum", "2025-26", None) == "BOS"
    finally:
        lookup.close()
