import datetime as _dt
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shared.store as _store
from shared.tools import team as _team

LAL = 1610612747
BOS = 1610612738

GAMES = [
    ("0022400001", "2024-10-22", "LAL vs. MIN", "W", 110, 103),
    ("0022400600", "2025-02-20", "LAL vs. BOS", "W", 120, 115),
    ("0022401200", "2025-04-11", "LAL vs. HOU", "W", 130, 125),
    ("0022401230", "2025-04-13", "LAL @ POR", "L", 81, 109),
]


def _seed(path: Path) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_hist_gamelogs (team_id BIGINT,"
            " team_abbreviation VARCHAR, game_id VARCHAR, game_date VARCHAR,"
            " matchup VARCHAR, wl VARCHAR, min DOUBLE, fgm INTEGER,"
            " fga INTEGER, fg_pct DOUBLE, fg3m INTEGER, fg3a INTEGER,"
            " fg3_pct DOUBLE, ftm INTEGER, fta INTEGER, ft_pct DOUBLE,"
            " oreb INTEGER, dreb INTEGER, reb INTEGER, ast INTEGER,"
            " stl INTEGER, blk INTEGER, tov INTEGER, pf INTEGER, pts INTEGER,"
            " _season VARCHAR, season_type VARCHAR)")
        for gid, date, matchup, wl, pts, opp in GAMES:
            con.execute(
                "INSERT INTO silver_hist_gamelogs VALUES (?, 'LAL', ?, ?, ?, ?,"
                " 30, 40, 80, 0.5, 10, 25, 0.4, 15, 20, 0.75,"
                " 8, 30, 38, 25, 7, 5, 14, 18, ?, '2024-25', 'regular-season')",
                [LAL, gid, date, matchup, wl, pts])
            con.execute(
                "INSERT INTO silver_hist_gamelogs VALUES (?, 'OPP', ?, ?, ?, ?,"
                " 30, 40, 80, 0.5, 10, 25, 0.4, 15, 20, 0.75,"
                " 8, 30, 38, 25, 7, 5, 14, 18, ?, '2024-25', 'regular-season')",
                [9000000000 + abs(hash(gid)) % 999, gid, date,
                 "OPP @ LAL", "L" if wl == "W" else "W", opp])
    finally:
        con.close()


@pytest.fixture
def hist_warehouse(tmp_path, monkeypatch):
    db = tmp_path / "hist.duckdb"
    _seed(db)

    def fake_connect(*args, **kwargs):
        return duckdb.connect(str(db), read_only=True)

    monkeypatch.setattr(_store, "connect", fake_connect)
    return db


def test_hist_slice_returns_most_recent_first(hist_warehouse):
    out = _team.get_team_game_log.invoke(
        {"team": "Lakers", "limit": 2, "season": "2024-25"})
    assert out["ok"], out.get("error")
    games = out["games"]
    assert len(games) == 2
    assert games[0]["date"] == "APR 13, 2025"
    assert games[1]["date"] == "APR 11, 2025"
    assert games[0]["opp_pts"] == 109
    assert games[1]["opp_pts"] == 125


def test_hist_window_meta_states_full_range(hist_warehouse):
    out = _team.get_team_game_log.invoke(
        {"team": "Lakers", "limit": 2, "season": "2024-25"})
    assert out["ok"], out.get("error")
    meta = out["meta"]
    assert meta["source"] == "warehouse:silver_hist_gamelogs"
    assert meta["season_games"] == 4
    assert meta["returned_games"] == 2
    assert meta["first_date"] == "2024-10-22"
    assert meta["last_date"] == "2025-04-13"
    assert meta["partial_window"] is True
    assert "4 games from 2024-10-22 to 2025-04-13" in meta["coverage_note"]
    assert "documented estimates" not in str(meta)


def test_hist_full_pull_clears_partial_flag(hist_warehouse):
    out = _team.get_team_game_log.invoke(
        {"team": "Lakers", "limit": 10, "season": "2024-25"})
    assert out["ok"], out.get("error")
    assert len(out["games"]) == 4
    assert out["meta"]["partial_window"] is False


def test_empty_window_error_names_coverage(hist_warehouse):
    out = _team.get_team_game_log.invoke(
        {"team": "Lakers", "limit": 5, "season": "2022-23"})
    assert out["ok"] is False
    assert out["error"].startswith("no regular-season games found for LAL")
