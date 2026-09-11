"""Record-computation regression tests for search_game_logs.

Root cause: rows.record summed WL over matched warehouse rows with no
Game_ID. A re-seed storing one game twice doubled the record, and the
unlabeled record let callers merge regular and playoff outputs
silently. Live case: "Denver's record when Jokic plays" must read
43-22 over 65, never 65-65 over 130.

Pure-helper tests are hermetic. Two integration tests run the real
tool read-only against the local warehouse. No LLM, no network.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.gamelog import (  # noqa: E402
    _dedupe_games,
    _record_for_scope,
    _record_note,
    search_game_logs,
)


def _row(gid, wl, pts=20.0):
    return {"game_id": gid, "wl": wl, "pts": pts}


def test_dedupe_collapses_duplicate_game_id():
    rows = [_row("0022500001", "W"), _row("0022500001", "W"),
            _row("0022500002", "L")]
    unique = _dedupe_games(rows)
    assert [g["game_id"] for g in unique] == ["0022500001", "0022500002"]
    assert _record_for_scope(unique, "regular") == {
        "w": 1, "l": 1, "games": 2, "scope": "regular"}


def test_dedupe_keeps_rows_without_game_id():
    rows = [_row(None, "W"), _row("", "L"), _row("0022500001", "W")]
    assert len(_dedupe_games(rows)) == 3


def test_record_carries_scope_label():
    assert _record_for_scope([_row("g1", "W")], "regular")["scope"] == "regular"
    assert _record_for_scope([_row("g1", "W")], "playoffs")["scope"] == "playoffs"


def test_record_note_only_when_games_below_total():
    assert _record_note(2, 2, "regular") is None
    note = _record_note(1, 2, "regular")
    assert note is not None
    assert "1 of 2" in note and "W/L" in note


def test_record_ignores_rows_without_wl_result():
    rows = [_row("g1", "W"), _row("g2", "")]
    record = _record_for_scope(rows, "regular")
    assert (record["w"], record["l"], record["games"]) == (1, 0, 1)
    assert _record_note(record["games"], len(rows), "regular") is not None


def test_jokic_record_43_22_live_read_only():
    res = search_game_logs.invoke({"player": "Nikola Jokic"})
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["scope"] == "regular"
    assert rows["record"] == {"w": 43, "l": 22, "games": 65,
                              "scope": "regular"}
    assert rows["total"] == 65
    assert "record_note" not in res["meta"]
    ids = [m["game_id"] for m in rows["matches"]]
    assert len(ids) == len(set(ids)) == rows["returned"] == 50


def test_playoff_record_scope_label_live_read_only():
    from app import store as _store
    from app.tools._core import coerce_player_id as _coerce
    from app.tools.splits import _resolve_name as _rname
    con = _store.connect(read_only=True)
    try:
        found = con.execute(
            "SELECT Player_ID, COUNT(*) FROM silver_playoff_gamelogs"
            " WHERE _season = '2025-26' GROUP BY Player_ID"
            " ORDER BY COUNT(*) DESC").fetchall()
    finally:
        con.close()
    pname = None
    for pid, _n in found:
        name = _rname(pid, "")
        if name and _coerce(name) == pid:
            pname = name
            break
    if pname is None:
        import pytest as _pt
        _pt.skip("no playoff rows in warehouse")
    res = search_game_logs.invoke({"player": pname, "playoffs": True})
    assert res["ok"] is True
    assert res["rows"]["scope"] == "playoffs"
    assert res["rows"]["record"]["scope"] == "playoffs"
