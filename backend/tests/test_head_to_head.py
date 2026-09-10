"""Head-to-head tests. Pure math is hermetic (monkeypatched loader);
one integration test reads the real warehouse to prove the wiring and
the small-sample honesty."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.tools.headtohead as h2h
from app.tools import get_head_to_head
from app.tools.headtohead import deltas, summarize, vs_opponent


def _row(matchup, date, wl="W", pts=20, reb=10, ast=5,
         fgm=10, fga=20, fta=0, tov=2):
    return {"MATCHUP": matchup, "GAME_DATE": date, "WL": wl,
            "Game_ID": "0022500001", "MIN": 36,
            "PTS": pts, "REB": reb, "AST": ast,
            "STL": 1, "BLK": 1, "TOV": tov,
            "FGM": fgm, "FGA": fga, "FG3M": 2, "FG3A": 6,
            "FTA": fta, "PLUS_MINUS": 5}


def test_summarize_math():
    rows = [
        _row("BOS @ NYK", "Jan 01, 2026", "W", pts=24, reb=13, ast=8,
             fgm=8, fga=13, fta=6),
        _row("BOS vs. NYK", "Feb 02, 2026", "L", pts=30, reb=5, ast=11,
             fgm=10, fga=20, fta=4),
    ]
    s = summarize(rows)
    assert s["gp"] == 2
    assert s["ppg"] == 27.0
    assert s["rpg"] == 9.0
    assert s["apg"] == 9.5
    assert s["fg_pct"] == round(18 / 33, 3)
    assert s["ts_pct"] == round(54 / (2 * (33 + 0.44 * 10)), 3)
    assert (s["w"], s["l"]) == (1, 1)


def test_summarize_empty():
    s = summarize([])
    assert s["gp"] == 0
    assert s["ppg"] == 0.0
    assert (s["w"], s["l"]) == (0, 0)


def test_deltas_math():
    opp = {"ppg": 30.0, "rpg": 10.0, "apg": 5.0,
           "fg_pct": 0.5, "ts_pct": 0.6}
    base = {"ppg": 20.0, "rpg": 8.0, "apg": 4.0,
            "fg_pct": 0.45, "ts_pct": 0.58}
    d = deltas(opp, base)
    assert d == {"ppg": 10.0, "rpg": 2.0, "apg": 1.0,
                 "fg_pct": 0.05, "ts_pct": 0.02}


def test_vs_opponent_filters_home_and_away():
    rows = [
        _row("BOS @ NYK", "Jan 01, 2026"),
        _row("BOS vs. NYK", "Feb 02, 2026"),
        _row("BOS @ MIA", "Mar 03, 2026"),
    ]
    kept = vs_opponent(rows, "NYK")
    assert [r["MATCHUP"] for r in kept] == ["BOS @ NYK", "BOS vs. NYK"]


def test_vs_opponent_never_teammates_side():
    # A player traded mid-season keeps only games where the trailing
    # token is the opponent, not the old or new team.
    rows = [
        _row("NYK @ BOS", "Jan 01, 2026"),   # player was on NYK; BOS is opp
        _row("BOS @ NYK", "Feb 02, 2026"),   # now on BOS; NYK is opp
        _row("BOS @ MIA", "Mar 03, 2026"),
    ]
    assert len(vs_opponent(rows, "NYK")) == 1
    assert vs_opponent(rows, "NYK")[0]["MATCHUP"] == "BOS @ NYK"


def _fake_season(monkeypatch):
    """6 games vs NYK (all wins, 20/10/5 on 50% FG) plus 4 other games
    (all losses, 30/6/7 on 50% FG)."""
    nyk = [_row(f"BOS @ NYK" if i % 2 else "BOS vs. NYK",
                f"Jan {i + 1:02d}, 2026", "W", pts=20, reb=10, ast=5,
                fgm=10, fga=20, fta=0)
           for i in range(6)]
    other = [_row("BOS @ MIA", f"Feb {i + 1:02d}, 2026", "L", pts=30,
                  reb=6, ast=7, fgm=15, fga=30, fta=0)
             for i in range(4)]
    monkeypatch.setattr(h2h, "_load_player_games", lambda pid, season: nyk + other)


def test_tool_averages_deltas_record(monkeypatch):
    _fake_season(monkeypatch)
    res = get_head_to_head.invoke({"player": "Jayson Tatum",
                                   "opponent": "Knicks"})
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["opponent"] == "NYK"
    assert rows["vs_opponent"]["gp"] == 6
    assert rows["vs_opponent"]["ppg"] == 20.0
    assert rows["vs_opponent"]["rpg"] == 10.0
    assert rows["vs_opponent"]["ts_pct"] == 0.5
    assert rows["team_record"] == "6-0"
    assert len(rows["games"]) == 6
    assert rows["season_baseline"]["gp"] == 10
    assert rows["season_baseline"]["ppg"] == 24.0
    assert rows["deltas"] == {"ppg": -4.0, "rpg": 1.6, "apg": -0.8,
                              "fg_pct": 0.0, "ts_pct": 0.0}
    assert rows["small_sample"] is False
    assert rows["note"] is None
    # Most recent game first.
    dates = [g["date"] for g in rows["games"]]
    assert dates == sorted(dates, reverse=True)


def test_tool_small_sample_flagged(monkeypatch):
    one = [_row("BOS @ NYK", "Jan 01, 2026", "L", pts=24, reb=13, ast=8)]
    monkeypatch.setattr(h2h, "_load_player_games", lambda pid, season: one)
    res = get_head_to_head.invoke({"player": "Jayson Tatum",
                                   "opponent": "NYK"})
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["small_sample"] is True
    assert rows["team_record"] == "0-1"
    assert rows["note"] and "1 game" in rows["note"]


def test_tool_zero_games_vs_opponent_still_honest(monkeypatch):
    games = [_row("BOS @ MIA", f"Jan {i + 1:02d}, 2026") for i in range(3)]
    monkeypatch.setattr(h2h, "_load_player_games", lambda pid, season: games)
    res = get_head_to_head.invoke({"player": "Jayson Tatum",
                                   "opponent": "NYK"})
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["vs_opponent"]["gp"] == 0
    assert rows["games"] == []
    assert rows["small_sample"] is True


def test_tool_unknown_player_rejected():
    res = get_head_to_head.invoke({"player": "Player McNotreal zzz",
                                   "opponent": "NYK"})
    assert res["ok"] is False
    assert "unknown player" in res["error"]


def test_tool_unknown_team_rejected():
    res = get_head_to_head.invoke({"player": "Jayson Tatum",
                                   "opponent": "ZZZ"})
    assert res["ok"] is False
    assert "unknown team" in res["error"]


def test_tool_no_gamelogs_for_resolved_player(monkeypatch):
    monkeypatch.setattr(h2h, "_load_player_games", lambda pid, season: [])
    res = get_head_to_head.invoke({"player": "Jayson Tatum",
                                   "opponent": "NYK"})
    assert res["ok"] is False
    assert "no gamelog data" in res["error"]


def test_integration_tatum_vs_knicks_real_warehouse():
    res = get_head_to_head.invoke({"player": "Tatum", "opponent": "Knicks"})
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["player"] == "Jayson Tatum"
    assert rows["opponent"] == "NYK"
    opp = rows["vs_opponent"]
    assert opp["gp"] == len(rows["games"])
    assert opp["gp"] < 5 and rows["small_sample"] is True
    assert rows["note"] and str(opp["gp"]) in rows["note"]
    assert rows["season_baseline"]["gp"] > opp["gp"]
    w, l = (int(x) for x in rows["team_record"].split("-"))
    assert w + l == opp["gp"]
    assert all(g["pts"] >= 0 for g in rows["games"])
    assert res["meta"]["source"] == "warehouse"
    assert res["meta"]["season"] == "2025-26"
