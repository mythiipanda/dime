"""Comps engine tests. Read the real warehouse; skip if leaders are absent."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import tools

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
