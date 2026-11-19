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
    return [
        ("Zero GP Zombie", "ZZZ", 0, 600.0, 115.0, 120.0, "2025-26"),
        ("Low Floor 499", "XYZ", 40, 499.0, 119.0, 110.0, "2025-26"),
        ("Hard Floor 500", "ABC", 40, 500.0, 118.0, 111.0, "2025-26"),
        ("Default 999", "DEF", 40, 999.0, 117.5, 112.0, "2025-26"),
        ("Default 1000", "GHI", 82, 1000.0, 117.0, 113.0, "2025-26"),
        ("Caller Floor 1500", "JKL", 60, 1500.0, 116.0, 114.0, "2025-26"),
        ("Clamp Ceil 4000", "MNO", 82, 4000.0, 110.0, 140.0, "2025-26"),
        ("Mid 1000 A", "PQR", 80, 1000.0, 112.0, 121.0, "2025-26"),
        ("Mid 1200 B", "STU", 40, 1200.0, 112.0, 122.0, "2025-26"),
        ("Def Low", "VWX", 50, 1000.0, 105.0, 95.0, "2025-26"),
        ("Def High", "YZA", 50, 1100.0, 106.0, 104.0, "2025-26"),
        ("Other Season", "OLD", 82, 2000.0, 130.0, 130.0, "2024-25"),
        ("Display Probe", "DSP", 40, 1200.0, 111.0, 123.0, "2025-26"),
    ]


@pytest.fixture()
def warehouse(tmp_path, monkeypatch):
    db = tmp_path / "ratings_minutes.duckdb"
    con = duckdb.connect(str(db))
    try:
        con.execute(
            "CREATE TABLE silver_advanced ("
            "PLAYER_NAME TEXT, TEAM_ABBREVIATION TEXT, GP INTEGER, "
            "MIN DOUBLE, OFF_RATING DOUBLE, DEF_RATING DOUBLE, _season TEXT)"
        )
        con.executemany(
            "INSERT INTO silver_advanced VALUES (?, ?, ?, ?, ?, ?, ?)",
            _sample_rows(),
        )
    finally:
        con.close()
    monkeypatch.setattr(_store, "DB_PATH", db)
    monkeypatch.setattr(_store, "LOCK_PATH", tmp_path / ".write.lock")
    monkeypatch.setattr(_core, "last_completed_season", lambda: SEASON)
    return db


def _names(result):
    return [row["PLAYER"] for row in result["rows"]]


def test_zero_min_minutes_still_enforces_500(warehouse):
    result = _league.get_player_ratings.invoke(
        {"season": SEASON, "metric": "offense", "min_minutes": 0}
    )
    names = _names(result)
    assert "Low Floor 499" not in names
    assert "Hard Floor 500" in names
    assert result["meta"]["qualification"] == "500+ total minutes"


def test_default_floor_is_1000(warehouse):
    result = _league.get_player_ratings.invoke({"season": SEASON, "metric": "offense"})
    names = _names(result)
    assert "Default 999" not in names
    assert "Hard Floor 500" not in names
    assert "Default 1000" in names


def test_caller_can_raise_floor_to_1500(warehouse):
    result = _league.get_player_ratings.invoke(
        {"season": SEASON, "metric": "offense", "min_minutes": 1500}
    )
    assert set(_names(result)) == {"Caller Floor 1500", "Clamp Ceil 4000"}


def test_caller_floor_clamped_to_4000(warehouse):
    result = _league.get_player_ratings.invoke(
        {"season": SEASON, "metric": "offense", "min_minutes": 9000}
    )
    assert _names(result) == ["Clamp Ceil 4000"]


def test_other_season_excluded(warehouse):
    for metric in ("offense", "defense"):
        result = _league.get_player_ratings.invoke(
            {"season": SEASON, "metric": metric, "min_minutes": 500}
        )
        assert "Other Season" not in _names(result)
        assert all(row["TEAM"] != "OLD" for row in result["rows"])


def test_offensive_rating_descending(warehouse):
    result = _league.get_player_ratings.invoke({"season": SEASON, "metric": "offense"})
    offs = [row["OFF_RATING"] for row in result["rows"]]
    assert offs == sorted(offs, reverse=True)
    assert _names(result)[:2] == ["Default 1000", "Caller Floor 1500"]


def test_defensive_rating_ascending(warehouse):
    result = _league.get_player_ratings.invoke({"season": SEASON, "metric": "defense"})
    defs = [row["DEF_RATING"] for row in result["rows"]]
    assert defs == sorted(defs)
    assert _names(result)[:2] == ["Def Low", "Def High"]


def test_same_rating_tiebreak_prefers_total_minutes(warehouse):
    result = _league.get_player_ratings.invoke({"season": SEASON, "metric": "offense"})
    by_name = {row["PLAYER"]: row for row in result["rows"]}
    assert by_name["Mid 1200 B"]["OFF_RATING"] == by_name["Mid 1000 A"]["OFF_RATING"]
    assert by_name["Mid 1200 B"]["RANK"] < by_name["Mid 1000 A"]["RANK"]


def test_mpg_and_minutes_display(warehouse):
    result = _league.get_player_ratings.invoke({"season": SEASON, "metric": "offense"})
    by_name = {row["PLAYER"]: row for row in result["rows"]}
    probe = by_name["Display Probe"]
    assert probe["MPG"] == 30
    assert probe["MINUTES"] == 1200


def test_zero_gp_mpg_is_zero(warehouse):
    result = _league.get_player_ratings.invoke(
        {"season": SEASON, "metric": "offense", "min_minutes": 500}
    )
    by_name = {row["PLAYER"]: row for row in result["rows"]}
    zombie = by_name["Zero GP Zombie"]
    assert zombie["MPG"] == 0
    assert zombie["MINUTES"] == 600


def test_limit_preserved(warehouse):
    result = _league.get_player_ratings.invoke(
        {"season": SEASON, "metric": "offense", "limit": 2}
    )
    assert len(result["rows"]) == 2
    assert [row["RANK"] for row in result["rows"]] == [1, 2]
