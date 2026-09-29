from pathlib import Path

import duckdb
import pytest


def build_warehouse(path):
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE silver_advanced ("
        "PLAYER_NAME VARCHAR, TEAM_ABBREVIATION VARCHAR, GP INTEGER, "
        "MIN DOUBLE, OFF_RATING DOUBLE, DEF_RATING DOUBLE, _season VARCHAR, "
        "_source VARCHAR, _fetched_at VARCHAR)"
    )
    for row in [
        ("Aldo Vance", "CAP", 70, 32.0, 122.4, 103.1),
        ("Bram Kessler", "CAP", 68, 31.0, 120.8, 105.6),
        ("Cato Merrill", "RIO", 72, 29.0, 119.3, 107.9),
        ("Dain Okafor", "RIO", 65, 28.0, 117.7, 109.4),
        ("Elif Sorren", "BAY", 71, 27.0, 116.2, 111.8),
        ("Finn Calloway", "BAY", 66, 26.0, 114.9, 113.2),
    ]:
        con.execute(
            "INSERT INTO silver_advanced VALUES "
            "(?, ?, ?, ?, ?, ?, '2025-26', 'fixture', '2026-04-14T00:00:00Z')",
            list(row),
        )
    con.execute(
        "CREATE TABLE silver_playoffs ("
        "TEAM_ID INTEGER, TEAM_NAME VARCHAR, GAME_ID VARCHAR, PTS INTEGER, "
        "FGA INTEGER, FTA INTEGER, OREB INTEGER, TOV INTEGER, "
        "_season VARCHAR, _fetched_at VARCHAR)"
    )
    for row in [
        (1, "Capital City Stars", "0042500101", 112, 88, 22, 9, 13),
        (2, "Rio Grande Rays", "0042500101", 104, 85, 20, 11, 15),
        (1, "Capital City Stars", "0042500102", 118, 90, 24, 8, 12),
        (2, "Rio Grande Rays", "0042500102", 110, 87, 21, 10, 14),
    ]:
        con.execute(
            "INSERT INTO silver_playoffs VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, '2025-26', '2026-06-01T00:00:00Z')",
            list(row),
        )
    con.execute(
        "CREATE TABLE silver_team_ratings ("
        "TEAM_ID INTEGER, TEAM_NAME VARCHAR, GP INTEGER, W INTEGER, L INTEGER, "
        "OFF_RATING DOUBLE, DEF_RATING DOUBLE, NET_RATING DOUBLE, PACE DOUBLE, "
        "TS_PCT DOUBLE, TM_TOV_PCT DOUBLE, OFF_RATING_RANK INTEGER, "
        "DEF_RATING_RANK INTEGER, NET_RATING_RANK INTEGER, TS_PCT_RANK INTEGER, "
        "TM_TOV_PCT_RANK INTEGER, _season VARCHAR, _source VARCHAR, "
        "_fetched_at VARCHAR)"
    )
    for row in [
        (1, "Capital City Stars", 82, 58, 24, 119.8, 110.2, 9.6, 99.1, 0.601, 12.4, 1, 4, 1, 2, 6),
        (2, "Rio Grande Rays", 82, 52, 30, 117.3, 111.5, 5.8, 98.4, 0.589, 13.1, 3, 8, 3, 5, 11),
        (3, "Bay City Fog", 82, 47, 35, 115.9, 112.8, 3.1, 97.9, 0.583, 13.8, 6, 12, 6, 8, 15),
    ]:
        con.execute(
            "INSERT INTO silver_team_ratings VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '2025-26', 'fixture', '2026-04-14T00:00:00Z')",
            list(row),
        )
    con.execute(
        "CREATE TABLE silver_hist_gamelogs ("
        "team_abbreviation VARCHAR, game_date VARCHAR, wl VARCHAR, _season VARCHAR)"
    )
    for game_date, wl in [
        ("2025-10-22", "W"),
        ("2025-10-23", "L"),
        ("2025-10-25", "W"),
        ("2025-10-29", "L"),
        ("2025-10-30", "W"),
    ]:
        con.execute(
            "INSERT INTO silver_hist_gamelogs VALUES ('DEN', ?, ?, '2025-26')",
            [game_date, wl],
        )
    con.close()


def clear_warehouse_caches():
    from shared import store
    from v2.api import routes
    store.warehouse_identity_cache_clear()
    routes.runtime_warehouse_identity.cache_clear()
    routes.runtime_asset_manifest.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def hermetic_warehouse(tmp_path_factory):
    from shared import store
    warehouse_path = tmp_path_factory.mktemp("warehouse") / "warehouse.duckdb"
    build_warehouse(warehouse_path)
    original = store.DB_PATH
    store.DB_PATH = warehouse_path
    clear_warehouse_caches()
    yield warehouse_path
    store.DB_PATH = original
    clear_warehouse_caches()
