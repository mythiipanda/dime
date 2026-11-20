import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.tools._core import is_scope_game  # noqa: E402
from shared.tools import gamelog  # noqa: E402
from shared.tools.league import get_elo_standings  # noqa: E402

SEASON = "2025-26"


def test_scope_rule_table():
    assert is_scope_game("0022500001", "regular") is True
    assert is_scope_game("0022500001", "playoffs") is False
    assert is_scope_game("0042500101", "playoffs") is True
    assert is_scope_game("0042500101", "playoff") is True
    assert is_scope_game("0042500101", "regular") is False
    assert is_scope_game("0022500001", "regular-season") is True
    assert is_scope_game("0012500001", "regular") is False
    assert is_scope_game("0012500001", "playoffs") is False
    assert is_scope_game("0032500001", "regular") is False
    assert is_scope_game("202510220MIN", "regular") is True
    assert is_scope_game("202510220MIN", "playoffs") is True
    assert is_scope_game("bbref-2025-10-22-MIN-BOS", "regular") is True
    assert is_scope_game("", "regular") is True
    assert is_scope_game(None, "playoffs") is True


def _seed_scope_tables(wh: Path):
    cols = ("GAME_DATE", "Game_ID", "MATCHUP", "WL", "MIN", "FGM", "FGA",
            "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB", "REB", "AST",
            "STL", "BLK", "TOV", "PF", "PTS", "PLUS_MINUS")
    con = duckdb.connect(str(wh))
    try:
        for table in ("silver_player_gamelogs", "silver_playoff_gamelogs"):
            con.execute(
                "CREATE TABLE " + table + " (Player_ID INTEGER, "
                + ", ".join(c + " VARCHAR" for c in cols) + ", _season TEXT)")
        regular = ("Oct 22, 2025", "0022500001", "MIN vs. BOS", "W", "24:00",
                   "9", "18", "2", "6", "5", "6", "1", "5", "6", "8", "2",
                   "1", "3", "2", "25", "7.0")
        playoff = ("Apr 20, 2026", "0042500101", "MIN at BOS", "L", "24:00",
                   "9", "18", "2", "6", "5", "6", "1", "5", "6", "8", "2",
                   "1", "3", "2", "25", "-3.0")
        external = ("Oct 24, 2025", "202510240MIN", "MIN vs. LAL", "W", "24:00",
                    "9", "18", "2", "6", "5", "6", "1", "5", "6", "8", "2",
                    "1", "3", "2", "25", "4.0")
        for row in (regular, playoff, external):
            con.execute(
                "INSERT INTO silver_player_gamelogs VALUES (23, "
                + ", ".join("?" for _ in row) + ", ?)", (*row, SEASON))
        for row in (playoff, regular):
            con.execute(
                "INSERT INTO silver_playoff_gamelogs VALUES (23, "
                + ", ".join("?" for _ in row) + ", ?)", (*row, SEASON))
        con.execute(
            "CREATE TABLE silver_hist_gamelogs (team_abbreviation VARCHAR, "
            "game_id VARCHAR, game_date VARCHAR, matchup VARCHAR, wl VARCHAR, "
            "plus_minus DOUBLE, _season TEXT)")
        hist = [
            ("BOS", "0022500001", "Oct 22, 2025", "BOS vs. NYK", "W", 5.0),
            ("NYK", "0022500001", "Oct 22, 2025", "NYK at BOS", "L", -5.0),
            ("BOS", "0042500101", "Apr 20, 2026", "BOS at NYK", "L", -3.0),
            ("NYK", "0042500101", "Apr 20, 2026", "NYK vs. BOS", "W", 3.0),
        ]
        for row in hist:
            con.execute("INSERT INTO silver_hist_gamelogs VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (*row, SEASON))
    finally:
        con.close()


@pytest.fixture()
def warehouse(monkeypatch, tmp_path):
    wh = tmp_path / "wh.duckdb"
    _seed_scope_tables(wh)
    monkeypatch.setattr(store, "connect",
                        lambda **_kw: duckdb.connect(str(wh)))
    return wh


def test_regular_gamelogs_exclude_playoff_game_ids(warehouse):
    ids = [g["game_id"] for g in gamelog._load_games(
        "silver_player_gamelogs", SEASON, 23)]
    assert ids == ["202510240MIN", "0022500001"]


def test_playoff_gamelogs_exclude_regular_game_ids(warehouse):
    ids = [g["game_id"] for g in gamelog._load_games(
        "silver_playoff_gamelogs", SEASON, 23)]
    assert ids == ["0042500101"]


def test_elo_standings_exclude_playoff_games(warehouse):
    res = get_elo_standings.invoke({"season": SEASON})
    assert res["ok"] is True
    table = {row["abbr"]: row for row in res["rows"]}
    assert (table["BOS"]["W"], table["BOS"]["L"]) == (1, 0)
    assert (table["NYK"]["W"], table["NYK"]["L"]) == (0, 1)
