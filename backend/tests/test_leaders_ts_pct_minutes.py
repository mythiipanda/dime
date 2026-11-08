import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store as _store
from shared.tools import _core
from shared.tools import league as _league

SEASON = "2025-26"


def _sample_rows():
    # silver_advanced is Totals basis per the declared producer (no per_mode):
    # MIN is the season TOTAL minutes, not per-game. Fixture encodes that
    # contract deliberately (R927 prereg; not universal production proof).
    return [
        ("Scrub 600", "AAA", 60, 600.0, 0.75, SEASON),
        ("Scrub 999", "BBB", 74, 999.0, 0.70, SEASON),
        ("Floor 1000", "CCC", 100, 1000.0, 0.80, SEASON),
        ("Full Season", "DDD", 70, 2100.0, 0.70, SEASON),
        ("Tie High", "EEE", 56, 1400.0, 0.60, SEASON),
        ("Tie Low", "FFF", 80, 1200.0, 0.60, SEASON),
        ("Zero GP Zombie", "ZZZ", 0, 2100.0, 0.50, SEASON),
        ("Old Star", "OLD", 70, 2100.0, 0.99, "2024-25"),
    ]


@pytest.fixture()
def warehouse(tmp_path, monkeypatch):
    db = tmp_path / "ts_pct_minutes.duckdb"
    con = duckdb.connect(str(db))
    try:
        con.execute(
            "CREATE TABLE silver_advanced ("
            "PLAYER_NAME TEXT, TEAM_ABBREVIATION TEXT, GP INTEGER, "
            "MIN DOUBLE, TS_PCT DOUBLE, _season TEXT)"
        )
        con.executemany(
            "INSERT INTO silver_advanced VALUES (?, ?, ?, ?, ?, ?)",
            _sample_rows(),
        )
    finally:
        con.close()
    monkeypatch.setattr(_store, "DB_PATH", db)
    monkeypatch.setattr(_store, "LOCK_PATH", tmp_path / ".write.lock")
    monkeypatch.setattr(_core, "last_completed_season", lambda: SEASON)
    return db


def _call(**kwargs):
    payload = {"stat_category": "TS_PCT", "season": SEASON}
    payload.update(kwargs)
    return _league.get_leaders.invoke(payload)


def _names(result):
    return [row["PLAYER"] for row in result["rows"]]


def test_sub_1000_total_minute_rows_are_excluded_by_default(warehouse):
    result = _call()
    names = _names(result)
    assert "Scrub 600" not in names
    assert "Scrub 999" not in names
    assert "Floor 1000" in names
    assert "Tie High" in names
    assert "Tie Low" in names
    assert "Old Star" not in names


def test_default_board_orders_by_ts_then_total_minutes_desc(warehouse):
    names = _names(_call())
    assert names.index("Floor 1000") < names.index("Full Season")
    assert names.index("Full Season") < names.index("Tie High")
    assert names.index("Tie High") < names.index("Tie Low")
    assert names.index("Tie Low") < names.index("Zero GP Zombie")


def test_asc_direction_keeps_min_desc_tiebreak(warehouse):
    asc = _call(ranking_direction="asc")
    names = _names(asc)
    assert names[0] == "Zero GP Zombie"
    assert names.index("Tie High") < names.index("Tie Low")
    desc = _call(ranking_direction="desc")
    assert _names(desc)[0] == "Floor 1000"


def test_min_attempts_raises_floor_above_1000(warehouse):
    result = _call(min_attempts=2000)
    names = _names(result)
    assert names == ["Full Season", "Zero GP Zombie"]
    assert result["meta"]["qualification_floor"]["floor"] == 2000
    assert result["meta"]["qualification"] == "2,000+ total minutes"


def test_min_attempts_below_1000_keeps_league_floor(warehouse):
    result = _call(min_attempts=0)
    names = _names(result)
    assert "Scrub 999" not in names
    assert "Floor 1000" in names
    assert result["meta"]["qualification_floor"]["floor"] == 1000


def test_display_derives_from_total_minutes_contract(warehouse):
    result = _call()
    rows = {row["PLAYER"]: row for row in result["rows"]}
    full = rows["Full Season"]
    assert full["TOTAL_MINUTES"] == 2100.0
    assert full["MPG"] == pytest.approx(30.0)
    assert full["TS_PCT"] == pytest.approx(70.0)
    zombie = rows["Zero GP Zombie"]
    assert zombie["MPG"] == 0
    assert zombie["TOTAL_MINUTES"] == 2100.0


def test_narration_evidences_total_minutes_floor(warehouse):
    result = _call()
    assert result["ok"] is True
    answer = result["meta"]["deterministic_answer"]
    assert "1,000+ total minutes" in answer
    assert "1,000 total minutes over 100 games" in answer
    assert result["meta"]["qualification_floor"]["cleared_column"] == "TOTAL_MINUTES"
    assert result["meta"]["qualification_floor"]["metric"] == "total_minutes"


def test_season_binding_excludes_other_seasons(warehouse):
    result = _call()
    assert "Old Star" not in _names(result)
