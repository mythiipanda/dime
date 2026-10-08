
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store as _store  # noqa: E402
from shared.tools import tracking as _tracking  # noqa: E402

SEASON = "2025-26"
PID = 2544
TEAM_ID = 1610612737

IDENTITY_PLAYER = ["PLAYER_ID", "PLAYER_NAME", "TEAM_ID",
                   "TEAM_ABBREVIATION", "TEAM_NAME",
                   "GP", "W", "L", "MIN"]
DRIVES_FAMILY = ["DRIVES", "DRIVE_FGM", "DRIVE_FGA", "DRIVE_FG_PCT",
                 "DRIVE_FTM", "DRIVE_FTA", "DRIVE_FT_PCT",
                 "DRIVE_PTS", "DRIVE_PTS_PCT",
                 "DRIVE_PASSES", "DRIVE_PASSES_PCT",
                 "DRIVE_AST", "DRIVE_AST_PCT",
                 "DRIVE_TOV", "DRIVE_TOV_PCT",
                 "DRIVE_PF", "DRIVE_PF_PCT"]
CATCH_FAMILY = ["CATCH_SHOOT_FGM", "CATCH_SHOOT_FGA",
                "CATCH_SHOOT_FG_PCT", "CATCH_SHOOT_PTS",
                "CATCH_SHOOT_FG3M", "CATCH_SHOOT_FG3A",
                "CATCH_SHOOT_FG3_PCT", "CATCH_SHOOT_EFG_PCT"]


def _seed(con):
    con.execute(
        "CREATE TABLE silver_tracking_pt_stats ("
        "PLAYER_ID INTEGER, PLAYER_NAME TEXT, TEAM_ID INTEGER, "
        "TEAM_ABBREVIATION TEXT, TEAM_NAME TEXT, "
        "GP INTEGER, W INTEGER, L INTEGER, MIN DOUBLE, "
        "DRIVES INTEGER, DRIVE_FGM INTEGER, DRIVE_FGA INTEGER, "
        "DRIVE_FG_PCT DOUBLE, DRIVE_PTS DOUBLE, "
        "CATCH_SHOOT_FGM INTEGER, CATCH_SHOOT_FGA INTEGER, "
        "CATCH_SHOOT_FG_PCT DOUBLE, CATCH_SHOOT_PTS INTEGER, "
        "EFF_FG_PCT DOUBLE, POINTS INTEGER, "
        "_source TEXT, _season TEXT, _fetched_at TEXT, _entity TEXT)"
    )
    con.execute(
        "INSERT INTO silver_tracking_pt_stats VALUES "
        "(2544, 'LeBron James', 1610612747, 'LAL', 'Los Angeles Lakers', "
        "70, 47, 23, 2450.0, "
        "900, 410, 800, 0.512, 950.0, "
        "NULL, NULL, NULL, NULL, NULL, NULL, "
        "'seed', '2025-26', '2026-01-01', 'ptstats:player:Drives'),"
        "(2544, 'LeBron James', 1610612747, 'LAL', 'Los Angeles Lakers', "
        "70, 47, 23, 2450.0, "
        "NULL, NULL, NULL, NULL, NULL, "
        "120, 300, 0.400, 360, NULL, NULL, "
        "'seed', '2025-26', '2026-01-01', 'ptstats:player:CatchShoot'),"
        "(2544, 'LeBron James', 1610612747, 'LAL', 'Los Angeles Lakers', "
        "70, 47, 23, 2450.0, "
        "NULL, NULL, NULL, NULL, NULL, "
        "NULL, NULL, NULL, NULL, 0.590, 1800, "
        "'seed', '2025-26', '2026-01-01', 'ptstats:player:Efficiency'),"
        "(NULL, NULL, 1610612737, 'ATL', 'Atlanta Hawks', "
        "82, 46, 36, 19755.0, "
        "5679, 2500, 4900, 0.510, 5900.0, "
        "NULL, NULL, NULL, NULL, NULL, NULL, "
        "'seed', '2025-26', '2026-01-01', 'ptstats:team:Drives')"
    )
    con.execute(
        "CREATE TABLE silver_tracking_pt_defend ("
        "CLOSE_DEF_PERSON_ID INTEGER, PLAYER_NAME TEXT, "
        "PLAYER_LAST_TEAM_ABBREVIATION TEXT, "
        "GP INTEGER, FREQ DOUBLE, D_FGM DOUBLE, D_FGA DOUBLE, "
        "D_FG_PCT DOUBLE, NORMAL_FG_PCT DOUBLE, PCT_PLUSMINUS DOUBLE, "
        "_source TEXT, _season TEXT, _fetched_at TEXT, _entity TEXT)"
    )
    con.execute(
        "INSERT INTO silver_tracking_pt_defend VALUES "
        "(203954, 'Rudy Gobert', 'MIN', "
        "76, 1.0, 538.0, 1223.0, 0.440, 0.489, -0.050, "
        "'seed', '2025-26', '2026-01-01', 'ptdefend:Overall')"
    )


@pytest.fixture()
def warehouse(tmp_path, monkeypatch):
    db = tmp_path / "tracking.duckdb"
    con = duckdb.connect(str(db))
    try:
        _seed(con)
    finally:
        con.close()
    monkeypatch.setattr(_store, "DB_PATH", db)
    monkeypatch.setattr(_store, "LOCK_PATH", tmp_path / ".write.lock")
    return db


@pytest.fixture()
def empty_warehouse(tmp_path, monkeypatch):
    db = tmp_path / "empty.duckdb"
    con = duckdb.connect(str(db))
    try:
        con.execute("CREATE TABLE silver_boxscores (GAME_ID TEXT, _season TEXT)")
    finally:
        con.close()
    monkeypatch.setattr(_store, "DB_PATH", db)
    monkeypatch.setattr(_store, "LOCK_PATH", tmp_path / ".write.lock")
    return db


def _expected(db, sql, params=None):
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(sql, params or []).fetchall()
    finally:
        con.close()


def test_profile_player_single_measure_returns_curated_row(warehouse):
    res = _tracking.get_tracking_profile.invoke(
        {"player": str(PID), "season": SEASON, "measure_type": "Drives"})
    assert res["ok"] is True
    assert len(res["rows"]) == 1
    row = res["rows"][0]
    assert row["measure_type"] == "Drives"
    allowed = set(IDENTITY_PLAYER + DRIVES_FAMILY + ["measure_type"])
    assert set(row) <= allowed
    [[want]] = _expected(
        warehouse,
        "SELECT DRIVES FROM silver_tracking_pt_stats "
        "WHERE _season = ? AND _entity = ? AND PLAYER_ID = ?",
        [SEASON, "ptstats:player:Drives", PID])
    assert row["DRIVES"] == want
    for col in CATCH_FAMILY:
        assert col not in row


def test_profile_team_scope_returns_team_row(warehouse):
    res = _tracking.get_tracking_profile.invoke(
        {"team": "ATL", "season": SEASON, "measure_type": "Drives"})
    assert res["ok"] is True
    assert len(res["rows"]) == 1
    row = res["rows"][0]
    assert row["TEAM_ABBREVIATION"] == "ATL"
    assert row["TEAM_NAME"] == "Atlanta Hawks"
    [[want]] = _expected(
        warehouse,
        "SELECT DRIVES FROM silver_tracking_pt_stats "
        "WHERE _season = ? AND _entity = ? AND TEAM_ABBREVIATION = ?",
        [SEASON, "ptstats:team:Drives", "ATL"])
    assert row["DRIVES"] == want


def test_profile_empty_measure_returns_all_measures_curated(warehouse):
    res = _tracking.get_tracking_profile.invoke(
        {"player": str(PID), "season": SEASON, "measure_type": ""})
    assert res["ok"] is True
    kinds = {r["measure_type"] for r in res["rows"]}
    assert kinds == {"Drives", "CatchShoot", "Efficiency"}
    by_kind = {r["measure_type"]: r for r in res["rows"]}
    assert (set(by_kind["Drives"]) - {"measure_type"}
            <= set(IDENTITY_PLAYER + DRIVES_FAMILY))
    assert by_kind["Drives"]["DRIVES"] == 900
    assert by_kind["Drives"]["DRIVE_FGM"] == 410
    assert by_kind["Drives"]["DRIVE_PTS"] == 950.0
    for col in CATCH_FAMILY:
        assert col not in by_kind["Drives"]
    assert by_kind["Efficiency"]["POINTS"] == 1800


def test_profile_rejects_zero_or_two_subjects(warehouse):
    both = _tracking.get_tracking_profile.invoke(
        {"player": str(PID), "team": "ATL", "season": SEASON})
    assert both["ok"] is False
    neither = _tracking.get_tracking_profile.invoke({"season": SEASON})
    assert neither["ok"] is False


def test_profile_rejects_unknown_measure_type(warehouse):
    res = _tracking.get_tracking_profile.invoke(
        {"player": str(PID), "season": SEASON, "measure_type": "Nope"})
    assert res["ok"] is False
    assert "Drives" in res["error"]


def test_profile_unknown_player_is_not_ok(warehouse):
    res = _tracking.get_tracking_profile.invoke(
        {"player": "Nobody McNobodyface", "season": SEASON})
    assert res["ok"] is False


def test_profile_missing_table_degrades_without_rows(empty_warehouse):
    res = _tracking.get_tracking_profile.invoke(
        {"player": str(PID), "season": SEASON, "measure_type": "Drives"})
    assert res["ok"] is False
    assert res["rows"] == []
    assert "not available" in res["error"]


def test_profile_wrong_season_never_substitutes(warehouse):
    res = _tracking.get_tracking_profile.invoke(
        {"player": str(PID), "season": "2020-21", "measure_type": "Drives"})
    assert res["ok"] is False
    assert res["rows"] == []
    assert SEASON in res["error"]


def test_matchups_returns_defended_shot_profile(warehouse):
    res = _tracking.get_defensive_matchups.invoke(
        {"player": "203954", "season": SEASON})
    assert res["ok"] is True
    assert len(res["rows"]) == 1
    row = res["rows"][0]
    [[gp, freq, fgm, fga, dfg, norm, diff]] = _expected(
        warehouse,
        "SELECT GP, FREQ, D_FGM, D_FGA, D_FG_PCT, NORMAL_FG_PCT, "
        "PCT_PLUSMINUS FROM silver_tracking_pt_defend "
        "WHERE _season = ? AND CLOSE_DEF_PERSON_ID = ?",
        [SEASON, 203954])
    assert (row["GP"], row["FREQ"], row["D_FGM"], row["D_FGA"],
            row["D_FG_PCT"], row["NORMAL_FG_PCT"],
            row["PCT_PLUSMINUS"]) == (gp, freq, fgm, fga, dfg, norm, diff)
    assert row["PLAYER_NAME"] == "Rudy Gobert"


def test_matchups_unknown_player_is_not_ok(warehouse):
    res = _tracking.get_defensive_matchups.invoke(
        {"player": "Nobody McNobodyface", "season": SEASON})
    assert res["ok"] is False


def test_matchups_missing_table_degrades_without_rows(empty_warehouse):
    res = _tracking.get_defensive_matchups.invoke(
        {"player": "203954", "season": SEASON})
    assert res["ok"] is False
    assert res["rows"] == []
    assert "not available" in res["error"]


def test_tools_are_exported():
    from shared import tools as _tools

    assert "get_tracking_profile" in _tools.TOOL_NAMES
    assert "get_defensive_matchups" in _tools.TOOL_NAMES


def test_capabilities_are_registered():
    from v2.adapters.capabilities import CAPABILITIES

    assert CAPABILITIES["tracking_profile"].tool_name == "get_tracking_profile"
    assert CAPABILITIES["defensive_matchups"].tool_name == "get_defensive_matchups"
