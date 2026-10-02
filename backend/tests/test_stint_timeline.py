import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl
import pytest

from shared import store
from shared.tools.stints import get_stint_timeline

GAME = "0042500405"
HOME = 1610612759
AWAY = 1610612752


def _row(n, poss_start, poss_end, clock_in, clock_out, h_in, a_in,
         h_out, a_out):
    row = {
        "game_id": GAME,
        "stint_number": n,
        "poss_start": poss_start,
        "poss_end": poss_end,
        "period_in": 1,
        "clock_in": clock_in,
        "period_out": 1,
        "clock_out": clock_out,
        "clock_in_sec": 720.0,
        "clock_out_sec": 469.0,
        "duration_sec": 251.0,
        "home_team_id": HOME,
        "away_team_id": AWAY,
        "home_abbr": "SAS",
        "away_abbr": "NYK",
        "score_home_in": h_in,
        "score_away_in": a_in,
        "score_home_out": h_out,
        "score_away_out": a_out,
        "home_swing": (h_out - h_in) - (a_out - a_in),
    }
    home_ids = [1628368, 1630170, 1630577, 1641705, 1642264]
    away_ids = [1626157, 1628384, 1628404, 1628969, 1628973]
    for i, pid in enumerate(home_ids, 1):
        row[f"home_player_{i}"] = pid
    for i, pid in enumerate(away_ids, 1):
        row[f"away_player_{i}"] = pid
    return row


@pytest.fixture
def seeded(monkeypatch, tmp_path):
    db = tmp_path / "timeline.duckdb"
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    frame = pl.DataFrame([
        _row(1, 1, 14, "12:00", "7:49", 0, 0, 6, 5),
        _row(2, 15, 21, "7:29", "5:40", 6, 5, 11, 8),
    ])
    store.write_unit("silver_stints", frame, "2025-26", "t", GAME,
                     "game_id = ?", [GAME])
    return db


def test_rejects_short_game_id(seeded):
    res = get_stint_timeline.invoke({"game_id": "425"})
    assert res["ok"] is False
    assert "10-digit" in res["error"]


def test_rejects_blank_game_id(seeded):
    res = get_stint_timeline.invoke({"game_id": ""})
    assert res["ok"] is False
    assert "10-digit" in res["error"]


def test_unknown_game_names_available_seasons(seeded):
    res = get_stint_timeline.invoke({"game_id": "0022400001"})
    assert res["ok"] is False
    assert "2025-26" in res["error"]


def test_known_game_returns_stints_with_names(seeded):
    res = get_stint_timeline.invoke({"game_id": GAME})
    assert res["ok"] is True
    assert len(res["rows"]) == 2
    first = res["rows"][0]
    assert first["stint_number"] == 1
    assert first["clock_in"] == "12:00"
    assert first["clock_out"] == "7:49"
    assert first["home_players"] == [1628368, 1630170, 1630577, 1641705,
                                     1642264]
    assert first["away_players"] == [1626157, 1628384, 1628404, 1628969,
                                     1628973]
    assert len(first["home_player_names"]) == 5
    assert all(isinstance(n, str) and n for n in
               first["home_player_names"])
    assert first["home_swing"] == 1
    assert res["meta"]["final_home"] == 11
    assert res["meta"]["final_away"] == 8
    assert res["meta"]["season"] == "2025-26"


def test_real_resolver_names_pilot_starters(seeded):
    res = get_stint_timeline.invoke({"game_id": GAME})
    names = res["rows"][0]["home_player_names"]
    assert "Victor Wembanyama" in names
    assert "Jalen Brunson" in res["rows"][0]["away_player_names"]


def test_registered_in_tool_registry(seeded):
    from shared import tools

    assert "get_stint_timeline" in tools.TOOL_NAMES


def test_capability_registered(seeded):
    from v2.adapters import capabilities

    assert "stint_timeline" in capabilities.CAPABILITIES
    assert any(c.name == "stint_timeline" for c in capabilities._LIST)
    assert "stint_timeline" in capabilities.CAPABILITY_DESCRIPTIONS
