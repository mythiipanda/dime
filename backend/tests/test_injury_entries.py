import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.normalize_injuries import normalize, save, _return_estimate

BLOB = [{
    "id": "-56292", "status": "Day-To-Day", "date": "2026-07-19T00:14Z",
    "shortComment": "Gueye had foot surgery after a workout injury.",
    "longComment": "Gueye will be re-evaluated in 3-to-4 months.",
    "athlete": {
        "firstName": "Mouhamed", "lastName": "Gueye",
        "displayName": "Mouhamed Gueye", "shortName": "M. Gueye",
        "position": {"abbreviation": "F", "name": "Forward"},
        "team": {"abbreviation": "ATL", "displayName": "Atlanta Hawks"},
        "status": {"name": "Active", "type": "active"},
        "notes": {"items": [{"source": "RotoWire",
                             "injury": {"$ref": "http://x/athletes/4712863/injuries/-56292"}}]},
        "links": [{"href": "https://www.espn.com/nba/player/_/id/4712863/mouhamed-gueye"}],
    },
}]


def test_normalize_extracts_fields():
    import ast
    frame = normalize([(1, "Atlanta Hawks", str(BLOB))])
    assert frame.height == 1
    r = frame.row(0, named=True)
    assert r["PLAYER"] == "Mouhamed Gueye"
    assert r["TEAM_ABBR"] == "ATL"
    assert r["ESPN_ATHLETE_ID"] == "4712863"
    assert r["STATUS"] == "Day-To-Day"
    assert r["SOURCE"] == "RotoWire"
    assert "foot" in r["INJURY"] or "surgery" in r["INJURY"]
    assert r["RETURN_ESTIMATE"]


def test_return_estimate_patterns():
    assert "3-to-4 months" in _return_estimate(
        {"longComment": "re-evaluated in 3-to-4 months."})
    assert "season" in _return_estimate(
        {"longComment": "out for the remainder of the season."})
    assert _return_estimate({"shortComment": "day-to-day."}) == "day-to-day"


def test_save_into_scratch(tmp_path):
    import duckdb
    from shared import store

    db = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(db))
    con.execute("create table silver_injuries "
                "(id VARCHAR, display_name VARCHAR, injuries VARCHAR, "
                "_season VARCHAR)")
    con.execute("insert into silver_injuries values ('1','Atlanta Hawks',?, '2025-26')",
                [str(BLOB)])
    old_db = store.DB_PATH
    store.DB_PATH = db.resolve()
    store.LOCK_PATH = db.parent / ".write.lock"
    try:
        n = save(con)
    finally:
        store.DB_PATH = old_db
    rows = con.execute(
        "select PLAYER, TEAM_ABBR, STATUS, ESPN_ATHLETE_ID "
        "from silver_injury_entries").fetchall()
    con.close()
    assert n == 1
    assert rows == [("Mouhamed Gueye", "ATL", "Day-To-Day", "4712863")]
