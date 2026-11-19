
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.tools import league
from shared.tools.today import _movers_from_delta, normalize_movers

SEASON = "2025-26"
BASE = "2026-10-30"
LATEST = "2026-11-06"


def _rows(order):
    climbers_tied = [
        "Aaron Gordon",
        "Brandon Ingram",
        "Cade Cunningham",
        "Devin Booker",
        "Evan Mobley",
        "Giannis Antetokounmpo",
        "Jalen Brunson",
        "Kevin Durant",
        "Luka Doncic",
        "Nikola Jokic",
        "Paolo Banchero",
        "Stephen Curry",
    ]
    fallers_tied = [
        "Anthony Edwards",
        "Bam Adebayo",
        "Derrick White",
        "Draymond Green",
        "Ja Morant",
        "Jayson Tatum",
        "Jimmy Butler",
        "Kawhi Leonard",
        "Kristaps Porzingis",
        "Lebron James",
        "Tyrese Haliburton",
    ]
    rows = []
    rows.append(("Victor Wembanyama", "SAS", 100, 13, BASE, 120, 1))
    for i, name in enumerate(climbers_tied, start=2):
        rows.append((name, "T", 100, i + 5, BASE, 110, i))
    rows.append(("Trae Young", "ATL", 120, 4, BASE, 80, 14))
    for i, name in enumerate(fallers_tied, start=15):
        rows.append((name, "T", 100, i - 4, BASE, 90, i))
    rows.append(("Ace Bailey", "UTA", None, None, None, 60, 26))
    rows.append(("Cooper Flagg", "DAL", None, None, None, 58, 27))
    rows.append(("Dylan Harper", "SAS", None, None, None, 57, 27))
    rows.append(("Khaman Maluach", "PHX", None, None, None, 55, 28))
    if order == "reversed":
        return rows[::-1]
    return rows


def _run(monkeypatch, order):
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE leaderboard_snapshots(snapshot_date VARCHAR,"
        " player VARCHAR, team VARCHAR, pts INTEGER, rank INTEGER,"
        " season VARCHAR)"
    )
    for player, team, pts_base, rank_base, dbase, pts_now, rank_now in _rows(order):
        if dbase is not None:
            con.execute(
                "INSERT INTO leaderboard_snapshots VALUES (?,?,?,?,?,?)",
                [dbase, player, team, pts_base, rank_base, SEASON],
            )
        con.execute(
            "INSERT INTO leaderboard_snapshots VALUES (?,?,?,?,?,?)",
            [LATEST, player, team, pts_now, rank_now, SEASON],
        )
    monkeypatch.setattr(store, "connect", lambda read_only=None: con)
    result = league.get_leaderboard_deltas.invoke(
        {"season": SEASON, "days": 7}
    )
    try:
        con.close()
    except Exception:
        pass
    return result


def test_complete_movers_and_deterministic_order(monkeypatch):
    first = _run(monkeypatch, "forward")
    second = _run(monkeypatch, "reversed")
    assert first["ok"] is True
    rows = first["rows"]
    assert len(rows["climbers"]) == 13
    assert len(rows["fallers"]) == 12
    assert len(rows["new_entries"]) == 4
    assert rows["climbers"][0]["player"] == "Victor Wembanyama"
    assert rows["climbers"][0]["rank_change"] == 12
    tied_names = [c["player"] for c in rows["climbers"][1:]]
    assert tied_names == sorted(tied_names, key=lambda n: n.casefold())
    assert rows["fallers"][0]["player"] == "Trae Young"
    assert rows["fallers"][0]["rank_change"] == -10
    fall_tied = [f["player"] for f in rows["fallers"][1:]]
    assert fall_tied == sorted(fall_tied, key=lambda n: n.casefold())
    assert [n["player"] for n in rows["new_entries"]] == [
        "Ace Bailey",
        "Cooper Flagg",
        "Dylan Harper",
        "Khaman Maluach",
    ]
    assert first == second
    normalized = normalize_movers(first, SEASON)["rows"]
    assert len(normalized["climbers"]) == 13
    assert len(normalized["fallers"]) == 12
    today_top = _movers_from_delta(first, SEASON)
    assert len(today_top) == 6
    assert today_top[0]["PLAYER"] == "Victor Wembanyama"
    assert today_top[3]["PLAYER"] == "Trae Young"
