"""ELO engine and standings tests. Pure-math cases are hermetic with
literal expected values; the 2025-26 smoke runs against the warehouse
(completed season, 1315 paired games)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.league import (  # noqa: E402
    _build_elo,
    _elo_expected,
    _elo_game_shift,
    _elo_mov_mult,
    get_elo,
    get_elo_standings,
)


def test_expected_and_mov_basics():
    assert _elo_expected(0.0) == 0.5
    assert _elo_expected(100.0) == pytest.approx(0.6401, abs=1e-4)
    assert _elo_mov_mult(None, 0.0) == 1.0


def test_neutral_blowout():
    rows = [("A", "g1", "2025-10-20", "A at B", "W", 20),
            ("B", "g1", "2025-10-20", "B at A", "L", -20)]
    elo, wins, losses, mov_ok = _build_elo(rows)
    assert round(elo["A"], 2) == 1516.38
    assert round(elo["B"], 2) == 1483.62
    assert wins == {"A": 1} and losses == {"B": 1}
    assert mov_ok is True
    assert round(sum(elo.values()), 9) == 3000.0


def test_home_edge():
    rows = [("H", "g1", "2025-10-20", "H vs. R", "W", 3),
            ("R", "g1", "2025-10-20", "R at H", "L", -3)]
    elo, wins, losses, _ = _build_elo(rows)
    assert round(elo["H"], 2) == 1503.73
    assert round(elo["R"], 2) == 1496.27
    assert wins == {"H": 1} and losses == {"R": 1}


def test_underdog_shifts_more_than_favorite():
    upset = _elo_game_shift(1500.0, 1700.0, False, False, 10)
    favorite = _elo_game_shift(1700.0, 1500.0, False, False, 10)
    assert upset == pytest.approx(13.59, abs=0.01)
    assert favorite == pytest.approx(4.30, abs=0.01)
    assert upset > favorite


def test_mov_scales():
    blowout = _elo_game_shift(1500.0, 1500.0, False, False, 20)
    close = _elo_game_shift(1500.0, 1500.0, False, False, 3)
    assert blowout == pytest.approx(16.38, abs=0.01)
    assert close == pytest.approx(5.59, abs=0.01)
    assert blowout > close


def test_empty_season():
    res = get_elo_standings.invoke({"season": "1999-00"})
    assert res["ok"] is True
    assert res["rows"] == []


def test_unknown_opponent():
    res = get_elo_standings.invoke({"season": "2025-26", "opponent": "ZZZ"})
    assert res["ok"] is False
    assert "unknown team" in res["error"]


def test_real_2025_26_smoke():
    res = get_elo_standings.invoke({"season": "2025-26"})
    assert res["ok"] is True
    rows = res["rows"]
    assert len(rows) == 30
    for r in rows:
        assert r["games"] > 0
        assert 0 <= r["elo_win_pct"] <= 1
        assert 0 <= r["win_equiv"] <= 82
    elos = [r["elo"] for r in rows]
    # Displayed elos are ints; +-0.5 rounding dust over 30 teams.
    assert abs(sum(elos) - 45000) < 15.0
    assert elos == sorted(elos, reverse=True)
    assert res["anchor"] == {"abbr": "AVG", "elo": 1500}
    assert res["meta"]["games"] == 1315
    print("top-5:", rows[:5])
    okc = next(r for r in rows if r["abbr"] == "OKC")
    print("OKC:", okc)
    assert rows[0]["elo"] == 1816 and rows[0]["abbr"] == "NYK"
    assert okc["elo"] == 1775 and okc["win_equiv"] == 68.0
    # Same engine as get_elo: identical rounded ratings.
    elo_rows = get_elo.invoke({"season": "2025-26"})["rows"]
    assert {r["TEAM"]: r["ELO"] for r in elo_rows} == {
        r["abbr"]: r["elo"] for r in rows}


def test_opponent_anchored_spread():
    res = get_elo_standings.invoke({"season": "2025-26", "opponent": "BOS"})
    assert res["ok"] is True
    assert res["anchor"]["abbr"] == "BOS"
    anchor_elo = res["anchor"]["elo"]
    for r in res["rows"]:
        assert r["elo_implied_spread"] == round((r["elo"] - anchor_elo) / 28, 1)
    bos = next(r for r in res["rows"] if r["abbr"] == "BOS")
    assert bos["elo_implied_spread"] == 0.0
