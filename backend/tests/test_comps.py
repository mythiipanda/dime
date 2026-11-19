
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import tools

WH = Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"

BOX_COLS = {
    "scoring volume (PTS/36)": ("PTS", True),
    "rebounding (REB/36)": ("REB", True),
    "playmaking (AST/36)": ("AST", True),
    "steals (STL/36)": ("STL", True),
    "blocks (BLK/36)": ("BLK", True),
    "three-point volume (3PA/36)": ("FG3A", True),
    "foul drawing (FTA/36)": ("FTA", True),
    "turnovers (TOV/36)": ("TOV", True),
    "three-point efficiency": ("FG3_PCT", False),
    "free-throw efficiency": ("FT_PCT", False),
}
ADV_COLS = {
    "usage rate": "USG_PCT",
    "true shooting": "TS_PCT",
    "assist rate": "AST_PCT",
    "turnover rate": "TM_TOV_PCT",
    "player impact estimate": "PIE",
    "offensive rating": "OFF_RATING",
    "defensive rating": "DEF_RATING",
    "net rating": "NET_RATING",
}

def _leaders_count() -> int:
    import duckdb

    try:
        con = duckdb.connect(str(WH), read_only=True)
        try:
            return con.execute(
                "SELECT COUNT(*) FROM silver_leaders_pts"
                " WHERE _season = '2025-26'").fetchone()[0]
        finally:
            con.close()
    except Exception:
        return 0

def _require_warehouse() -> None:
    if _leaders_count() == 0:
        pytest.skip("silver_leaders_pts missing/empty")

def test_luka_comps_shape():
    _require_warehouse()
    res = tools.get_comps.invoke({"player_id": "Luka Doncic"})
    assert res["ok"] is True
    rows = res["rows"]
    assert len(rows) == 5
    sims = [r["similarity"] for r in rows]
    assert all(b < a for a, b in zip(sims, sims[1:]))
    assert all(r["PLAYER_ID"] != 1629029 for r in rows)
    for r in rows:
        assert {"archetype", "drivers", "similarity"} <= set(r)
        assert len(r["drivers"]) == 3

def test_luka_archetype_and_neighborhood():
    _require_warehouse()
    res = tools.get_comps.invoke({"player_id": "Luka Doncic"})
    assert res["ok"] is True
    assert res["player"]["archetype"] == "high-usage creator"
    allowed = {"high-usage creator", "high-usage scorer",
               "secondary creator", "floor general"}
    assert any(r["archetype"] in allowed for r in res["rows"])

def test_driver_values_match_warehouse():
    import duckdb

    _require_warehouse()
    res = tools.get_comps.invoke({"player_id": "Luka Doncic"})
    assert res["ok"] is True
    con = duckdb.connect(str(WH), read_only=True)
    try:
        lead = con.execute(
            "SELECT * FROM silver_leaders_pts WHERE _season = '2025-26'"
            " AND CAST(PLAYER_ID AS VARCHAR) = '1629029'").fetchdf().iloc[0]
        adv = con.execute(
            "SELECT * FROM silver_advanced WHERE _season = '2025-26'"
            " AND CAST(PLAYER_ID AS VARCHAR) = '1629029'").fetchdf().iloc[0]
    finally:
        con.close()
    checked = 0
    for d in res["rows"][0]["drivers"]:
        if d["stat"] in BOX_COLS:
            col, per36 = BOX_COLS[d["stat"]]
            expected = (36 * float(lead[col]) / float(lead["MIN"])
                        if per36 else float(lead[col]))
        elif d["stat"] in ADV_COLS:
            expected = float(adv[ADV_COLS[d["stat"]]])
        else:
            pytest.fail(f"unknown driver label {d['stat']}")
        assert abs(float(d["target"]) - expected) <= 0.15
        checked += 1
    assert checked == 3

def test_unknown_player():
    res = tools.get_comps.invoke({"player_id": "Not A Real Player XYZ"})
    assert res["ok"] is False
    assert "unknown player" in res["error"]

def test_missing_season():
    res = tools.get_comps.invoke(
        {"player_id": "Luka Doncic", "season": "2030-31"})
    assert res["ok"] is False

def test_synthetic_2009_season_note(monkeypatch):
    from shared.tools import _core as core_module
    from shared.tools import player as player_module

    leaders = [
        {"PLAYER_ID": 1001, "PLAYER": "Player One", "TEAM": "T1", "MIN": 1120.0,
         "PTS": 1300.0, "REB": 620.0, "AST": 550.0, "STL": 130.0, "BLK": 45.0,
         "FG3A": 160.0, "FTA": 320.0, "TOV": 160.0,
         "FG3_PCT": 0.37, "FT_PCT": 0.89},
        {"PLAYER_ID": 1002, "PLAYER": "Player Two", "TEAM": "T2", "MIN": 1080.0,
         "PTS": 1250.0, "REB": 580.0, "AST": 620.0, "STL": 110.0, "BLK": 60.0,
         "FG3A": 190.0, "FTA": 300.0, "TOV": 175.0,
         "FG3_PCT": 0.35, "FT_PCT": 0.85},
        {"PLAYER_ID": 1003, "PLAYER": "Player Three", "TEAM": "T3", "MIN": 1180.0,
         "PTS": 1400.0, "REB": 700.0, "AST": 430.0, "STL": 150.0, "BLK": 90.0,
         "FG3A": 80.0, "FTA": 380.0, "TOV": 190.0,
         "FG3_PCT": 0.31, "FT_PCT": 0.82},
        {"PLAYER_ID": 1004, "PLAYER": "Player Four", "TEAM": "T4", "MIN": 1010.0,
         "PTS": 1100.0, "REB": 520.0, "AST": 700.0, "STL": 90.0, "BLK": 30.0,
         "FG3A": 220.0, "FTA": 250.0, "TOV": 140.0,
         "FG3_PCT": 0.39, "FT_PCT": 0.91},
        {"PLAYER_ID": 1005, "PLAYER": "Player Five", "TEAM": "T5", "MIN": 1240.0,
         "PTS": 1550.0, "REB": 640.0, "AST": 480.0, "STL": 160.0, "BLK": 110.0,
         "FG3A": 120.0, "FTA": 420.0, "TOV": 210.0,
         "FG3_PCT": 0.33, "FT_PCT": 0.78},
        {"PLAYER_ID": 1006, "PLAYER": "Player Six", "TEAM": "T6", "MIN": 990.0,
         "PTS": 950.0, "REB": 730.0, "AST": 610.0, "STL": 100.0, "BLK": 25.0,
         "FG3A": 250.0, "FTA": 210.0, "TOV": 130.0,
         "FG3_PCT": 0.40, "FT_PCT": 0.87},
    ]

    def fake_read_df(sql, params):
        if "silver_leaders_pts" in sql:
            return list(leaders)
        return []

    monkeypatch.setattr(player_module, "_read_df", fake_read_df)
    monkeypatch.setattr(core_module, "last_completed_season", lambda: "2025-26")
    res = tools.get_comps.invoke({"player_id": 1001, "season": "2009-10"})
    assert res["ok"] is True
    assert res["meta"]["season"] == "2009-10"
    assert res["meta"]["notes"] == (
        "cross-era comps unavailable"
        "; advanced metrics unavailable, box-score features only")
    assert "2025-26" not in res["meta"]["notes"]
