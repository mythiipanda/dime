import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.tools.team import _competitive_lineup_nets

SEASON = "2024-25"
TEAM = 14
OPP = 99
OTHER = 88
UNIT = (1, 2, 3, 4, 5)
OPP_UNIT = (6, 7, 8, 9, 10)


def _connect(rows):
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE silver_hist_possessions ("
        "offense_team_id INTEGER, defense_team_id INTEGER, points INTEGER, "
        "off_player_1 INTEGER, off_player_2 INTEGER, off_player_3 INTEGER, "
        "off_player_4 INTEGER, off_player_5 INTEGER, "
        "def_player_1 INTEGER, def_player_2 INTEGER, def_player_3 INTEGER, "
        "def_player_4 INTEGER, def_player_5 INTEGER, "
        "garbage INTEGER, count_as_possession VARCHAR, _season VARCHAR)"
    )
    con.executemany(
        "INSERT INTO silver_hist_possessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return con


def _row(off_team, def_team, points, off_unit, def_unit, garbage, counted, season=SEASON):
    return [off_team, def_team, points, *off_unit, *def_unit, garbage, counted, season]


def _mixed_rows():
    rows = []
    for _ in range(100):
        rows.append(_row(TEAM, OPP, 1, UNIT, OPP_UNIT, 0, "true"))
        rows.append(_row(OPP, TEAM, 1, OPP_UNIT, UNIT, 0, "true"))
        rows.append(_row(TEAM, OPP, 3, UNIT, OPP_UNIT, 0, "false"))
        rows.append(_row(OPP, TEAM, 0, OPP_UNIT, UNIT, 0, "false"))
        rows.append(_row(TEAM, OPP, 3, UNIT, OPP_UNIT, 1, "true"))
        rows.append(_row(TEAM, OPP, 3, UNIT, OPP_UNIT, 0, "true", season="2023-24"))
        rows.append(_row(OTHER, OPP, 3, UNIT, OPP_UNIT, 0, "true"))
    return rows


def test_competitive_nets_exclude_noncounted(monkeypatch):
    con = _connect(_mixed_rows())
    monkeypatch.setattr(store, "connect", lambda *a, **k: con)
    result = _competitive_lineup_nets(TEAM, SEASON)
    assert result == {UNIT: (0.0, 200)}


def test_competitive_nets_counted_only_parity(monkeypatch):
    counted_rows = [r for r in _mixed_rows() if r[14] == "true" and r[15] == SEASON and r[13] == 0]
    con = _connect(counted_rows)
    monkeypatch.setattr(store, "connect", lambda *a, **k: con)
    assert _competitive_lineup_nets(TEAM, SEASON) == {UNIT: (0.0, 200)}


def test_competitive_nets_noncounted_only_returns_none(monkeypatch):
    rows = [_row(TEAM, OPP, 3, UNIT, OPP_UNIT, 0, "false") for _ in range(100)]
    con = _connect(rows)
    monkeypatch.setattr(store, "connect", lambda *a, **k: con)
    assert _competitive_lineup_nets(TEAM, SEASON) is None
