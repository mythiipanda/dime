
import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools.gamelog import (  # noqa: E402
    _dedupe_games,
    _record_for_scope,
    _record_note,
    search_game_logs,
)


def _row(gid, wl, pts=20.0):
    return {"game_id": gid, "wl": wl, "pts": pts}


def _full_row(gid, wl, date, pts=20.0, pid=2544, matchup="LAL vs. UTA"):
    d = _dt.date.fromisoformat(date)
    return {
        "player_id": pid, "game_id": gid, "date": d, "matchup": matchup,
        "opponent": "UTA", "home": True, "wl": wl, "min": 36.0,
        "pts": float(pts), "reb": 5.0, "ast": 5.0, "stl": 1.0, "blk": 1.0,
        "tov": 2.0, "pf": 2.0, "fgm": 8.0, "fga": 16.0, "fg3m": 2.0,
        "fg3a": 6.0, "ftm": 2.0, "fta": 2.0, "plus_minus": 4.0,
    }


def test_dedupe_collapses_duplicate_game_id():
    rows = [_full_row("0022500001", "W", "2026-03-01"),
            _full_row("0022500001", "W", "2026-03-01"),
            _full_row("0022500002", "L", "2026-03-03")]
    unique = _dedupe_games(rows)
    assert [g["game_id"] for g in unique] == ["0022500001", "0022500002"]
    assert _record_for_scope(unique, "regular") == {
        "w": 1, "l": 1, "games": 2, "scope": "regular"}


def test_dedupe_keeps_distinct_rows_without_game_id():
    rows = [_full_row(None, "W", "2026-03-01"),
            _full_row(None, "W", "2026-03-02")]
    assert len(_dedupe_games(rows)) == 2


def test_dedupe_collapses_identical_rows_without_game_id():
    rows = [_full_row(None, "W", "2026-03-01"),
            _full_row("", "W", "2026-03-01")]
    assert len(_dedupe_games(rows)) == 1


def test_dedupe_collapses_cross_seed_game_id_formats():
    rows = [_full_row("0022500001", "W", "2026-03-01"),
            _full_row("202603010LAL", "W", "2026-03-01")]
    assert len(_dedupe_games(rows)) == 1


def test_dedupe_keeps_same_statline_different_players():
    rows = [_full_row("g1", "W", "2026-03-01", pid=2544),
            _full_row("g1", "W", "2026-03-01", pid=201939)]
    assert len(_dedupe_games(rows)) == 2


def test_dedupe_frame_collapses_cross_seed_duplicates():
    try:
        import polars as pl
    except ImportError:
        return
    from shared.tools.gamelog import dedupe_game_log_frame

    def r(gid, date, pts):
        return {"Player_ID": 2544, "Game_ID": gid, "GAME_DATE": date,
                "MATCHUP": "LAL vs. UTA", "WL": "W", "PTS": pts, "REB": 5,
                "AST": 5, "_source": "bbref", "_season": "2025-26",
                "_fetched_at": "2026-09-27", "_entity": "player:2544"}

    rows = [r("0022500001", "Mar 1, 2026", 30),
            r("202603010LAL", "Mar 1, 2026", 30),
            r(None, "Mar 1, 2026", 30),
            r("0022500002", "Mar 3, 2026", 30),
            r("0022500002", "Mar 3, 2026", 30)]
    out = dedupe_game_log_frame(pl.DataFrame(rows))
    assert out.height == 2
    assert out["GAME_DATE"].to_list() == ["Mar 1, 2026", "Mar 3, 2026"]
    other = pl.DataFrame({"a": [1, 1, 2]})
    assert dedupe_game_log_frame(other).height == 3


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
    from shared import store as _store
    from shared.tools._core import coerce_player_id as _coerce
    from shared.tools.splits import _resolve_name as _rname
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
