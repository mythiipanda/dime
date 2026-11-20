import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.seed_draft_capital import _value_curve
from shared.sources.draft_picks import _abbr, _parse, _season_label

PAYLOAD = {
    "last_edited": "2026-10-03T00:00:00+00:00",
    "teams": [
        {"team": "SA", "picks": [
            {"draft_year": 2027, "round": 1, "status": "own",
             "held_by": [], "protection": None,
             "pooled": False, "conditional": False, "summary": "still theirs"},
            {"draft_year": 2028, "round": 2, "status": "traded",
             "held_by": ["OKC", "GS"], "protection": "Top-10 protected",
             "pooled": True, "conditional": True, "summary": "goes out"},
        ]},
        {"team": "NO", "picks": [
            {"draft_year": 2027, "round": 1, "status": "swap",
             "held_by": ["NY"], "protection": None,
             "pooled": False, "conditional": False, "summary": "swap"},
        ]},
    ],
}


def test_abbr_maps_source_codes():
    assert _abbr("SA") == "SAS"
    assert _abbr("GS") == "GSW"
    assert _abbr("NY") == "NYK"
    assert _abbr("OKC") == "OKC"
    assert _abbr("NBA") == "NBA"


def test_season_label_from_min_year():
    assert _season_label([2027, 2030]) == "2026-27"


def test_parse_rows_and_codes():
    frame = _parse(PAYLOAD)
    assert frame.height == 3
    sas = frame.filter(frame["ORIG_TEAM"] == "SAS").to_dicts()
    traded = next(r for r in sas if r["STATUS"] == "traded")
    assert traded["HELD_BY"] == "OKC;GSW"
    assert traded["POOLED"] is True
    assert traded["PROTECTION"] == "Top-10 protected"
    nop = frame.filter(frame["ORIG_TEAM"] == "NOP").to_dicts()[0]
    assert nop["STATUS"] == "swap"
    assert nop["HELD_BY"] == "NYK"


def test_value_curve_derives_slot_table():
    con = duckdb.connect()
    try:
        con.execute("CREATE TABLE silver_hist_draft (OVERALL_PICK INTEGER, ROUND_NUMBER INTEGER, PLAYER_NAME VARCHAR, SEASON INTEGER)")
        con.execute("CREATE TABLE silver_raptor_player (player_name VARCHAR, mp INTEGER, war_total DOUBLE)")
        con.execute("INSERT INTO silver_hist_draft VALUES (1, 1, 'Star Pick', 2000), (2, 1, 'Bust Pick', 2000), (31, 2, 'Deep Pick', 2000)")
        con.execute("INSERT INTO silver_raptor_player VALUES ('Star Pick', 20000, 40.0), ('Bust Pick', 500, 0.5), ('Deep Pick', 5000, 3.0)")
        frame = _value_curve(con)
    finally:
        con.close()
    rows = {r["SLOT"]: r for r in frame.to_dicts()}
    assert rows[1]["MEDIAN_CAREER_WAR"] == 40.0
    assert rows[1]["HIT_RATE"] == 1.0
    assert rows[1]["VALUE_INDEX"] == 1.0
    assert rows[2]["HIT_RATE"] == 0.0
    assert rows[31]["ROUND"] == 2
