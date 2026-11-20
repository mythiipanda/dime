import json
import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store  # noqa: E402
from shared.tools import possessions as possession_log  # noqa: E402

TABLE = "silver_possessions"


def _frame():
    return pl.DataFrame(
        [
            {
                "game_id": "0022400001",
                "possession_number": 1,
                "period": 1,
                "clock_in": "12:00",
                "clock_out": "11:37",
                "clock_in_sec": 720.0,
                "clock_out_sec": 697.0,
                "off_team_id": 1610612737,
                "def_team_id": 1610612738,
                "off_abbr": "ATL",
                "def_abbr": "BOS",
                "home_team_id": 1610612738,
                "away_team_id": 1610612737,
                "events": json.dumps(["PERIOD-START", "TIP", "MISS3"]),
                "points": 0,
                "wpa_delta": 0.001,
                "score_home_in": 0,
                "score_away_in": 0,
                "score_home_out": 0,
                "score_away_out": 0,
            },
            {
                "game_id": "0022400001",
                "possession_number": 2,
                "period": 1,
                "clock_in": "7:42",
                "clock_out": "7:41",
                "clock_in_sec": 462.0,
                "clock_out_sec": 461.0,
                "off_team_id": 1610612738,
                "def_team_id": 1610612737,
                "off_abbr": "BOS",
                "def_abbr": "ATL",
                "home_team_id": 1610612738,
                "away_team_id": 1610612737,
                "events": json.dumps(["MISS3", "TEAM-DREB"]),
                "points": 0,
                "wpa_delta": -0.002,
                "score_home_in": 10,
                "score_away_in": 11,
                "score_home_out": 10,
                "score_away_out": 11,
            },
            {
                "game_id": "0022400001",
                "possession_number": 3,
                "period": 2,
                "clock_in": "3:10",
                "clock_out": "3:00",
                "clock_in_sec": 190.0,
                "clock_out_sec": 180.0,
                "off_team_id": 1610612738,
                "def_team_id": 1610612737,
                "off_abbr": "BOS",
                "def_abbr": "ATL",
                "home_team_id": 1610612738,
                "away_team_id": 1610612737,
                "events": json.dumps(["TIP", "MAKE2"]),
                "points": 2,
                "wpa_delta": 0.01,
                "score_home_in": 81,
                "score_away_in": 75,
                "score_home_out": 83,
                "score_away_out": 75,
            },
        ]
    )


@pytest.fixture
def warehouse(monkeypatch, tmp_path):
    db = tmp_path / "possessions.duckdb"
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.write_unit(TABLE, _frame(), "2024-25", "nba_stats_pbp",
                     "game:0022400001", "game_id = ?", ["0022400001"])
    return db


def _call(**kwargs):
    return possession_log.get_possession_log.func(**kwargs)


def test_orders_by_possession_number(warehouse):
    result = _call(game_id="0022400001")
    assert result["ok"] is True
    assert [r["possession_number"] for r in result["rows"]] == [1, 2, 3]
    assert result["rows"][0]["events"] == ["PERIOD-START", "TIP", "MISS3"]
    assert result["meta"]["game_id"] == "0022400001"


def test_period_filter(warehouse):
    result = _call(game_id="0022400001", period=2)
    assert result["ok"] is True
    assert [r["possession_number"] for r in result["rows"]] == [3]
    assert result["meta"]["period"] == 2


def test_clock_range_filter_is_inclusive(warehouse):
    result = _call(game_id="0022400001", clock_range="12:00-4:00")
    assert result["ok"] is True
    assert [r["possession_number"] for r in result["rows"]] == [1, 2]
    result = _call(game_id="0022400001", period=1,
                   clock_range="7:42-7:42")
    assert [r["possession_number"] for r in result["rows"]] == [2]


def test_empty_filter_match_is_ok_not_no_coverage(warehouse):
    result = _call(game_id="0022400001", period=4)
    assert result["ok"] is True
    assert result["rows"] == []
    assert result["meta"]["possessions"] == 0
    assert "filters" in result["meta"]["note"]


def test_bad_clock_range_is_honest_error(warehouse):
    result = _call(game_id="0022400001", clock_range="late")
    assert result["ok"] is False
    assert result["rows"] == []


def test_no_coverage_refusal(warehouse):
    result = _call(game_id="0022400099")
    assert result["ok"] is False
    assert result["rows"] == []
    assert result["tool"] == "get_possession_log"
    assert "0022400099" in result["meta"]["deterministic_answer"]


def test_bad_game_id_is_honest_error(warehouse):
    result = _call(game_id="abc")
    assert result["ok"] is False
    assert result["rows"] == []
