"""Hermetic tests for get_rotation_check. No network, no warehouse.

All inputs are synthetic dicts driving the pure functions; the one
tool-level test monkeypatches the module fetch helpers.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio as _asyncio

from app import tools
from app.tools.team import (
    _assemble_rotation_report,
    _closing_candidates,
    _thin_rotation_flags,
    _tier_players,
    get_rotation_check,
)


def _player(name, minutes, mpg=None, diff=None, cached=True, pid=1, gp=60, pts=600.0):
    return {
        "PLAYER": name, "PLAYER_ID": pid, "GP": gp, "MIN": float(minutes),
        "MPG": float(mpg) if mpg is not None else round(float(minutes) / gp, 1),
        "PTS": float(pts), "ON": None, "OFF": None, "DIFF": diff,
        "CACHED": cached,
    }


def _fifteen():
    return [_player(f"P{i + 1}", 2000 - i * 100, pid=100 + i,
                    diff=1.0, cached=True) for i in range(15)]


def _unit(name, poss, net, best=False):
    return {
        "GROUP_NAME": name, "EST_MIN": poss / 2, "GP": 20, "poss": poss,
        "OFF_RATING": 115.0, "DEF_RATING": 115.0 - net,
        "NET_RATING": net, "PLUS_MINUS": 10,
        "is_best_net_unit": best, "flags": [],
    }


def test_tiers_split_top5_6_10_11_15():
    tiers = _tier_players(_fifteen())
    assert [p["PLAYER"] for p in tiers["core"]] == [f"P{i}" for i in range(1, 6)]
    assert [p["PLAYER"] for p in tiers["bench"]] == [f"P{i}" for i in range(6, 11)]
    assert [p["PLAYER"] for p in tiers["fringe"]] == [f"P{i}" for i in range(11, 16)]


def test_tiers_sort_by_min_desc():
    players = [_player("low", 100, pid=1), _player("high", 900, pid=2),
               _player("mid", 500, pid=3)]
    tiers = _tier_players(players)
    assert tiers["core"][0]["PLAYER"] == "high"
    assert tiers["core"][1]["PLAYER"] == "mid"


def test_thin_rotation_seven_man():
    players = ([_player(f"R{i}", 1500, mpg=25, pid=i) for i in range(7)]
               + [_player(f"B{i}", 200, mpg=4, pid=100 + i) for i in range(8)])
    flags = _thin_rotation_flags(players=players, most_used_share=0.1,
                                 bench_diffs=[], cached_onoff=10)
    assert any("thin rotation" in f for f in flags)


def test_heavy_reliance_share_040():
    players = [_player(f"R{i}", 1500, mpg=20, pid=i) for i in range(10)]
    flags = _thin_rotation_flags(players=players, most_used_share=0.40,
                                 bench_diffs=[], cached_onoff=10)
    assert any("heavy reliance" in f for f in flags)


def test_bench_drag_avg_minus4():
    players = [_player(f"R{i}", 1500, mpg=20, pid=i) for i in range(10)]
    flags = _thin_rotation_flags(players=players, most_used_share=0.1,
                                 bench_diffs=[-5.0, -4.0, -3.0],
                                 cached_onoff=10)
    assert any("bench drag" in f for f in flags)


def test_thin_onoff_coverage_5_of_10():
    players = [_player(f"R{i}", 1500, mpg=20, pid=i) for i in range(10)]
    flags = _thin_rotation_flags(players=players, most_used_share=0.1,
                                 bench_diffs=[], cached_onoff=5)
    assert any("on/off coverage thin" in f for f in flags)


def test_thin_flags_empty_no_crash():
    assert _thin_rotation_flags(players=[], most_used_share=0.0,
                                bench_diffs=[], cached_onoff=0) == []


def test_closing_candidates_best_net_first():
    units = [_unit("most-used", 500, 2.0, best=False),
             _unit("closers", 300, 10.0, best=True),
             _unit("tiny", 50, 99.0, best=False)]
    out = _closing_candidates(units, 5, 100)
    assert [u["GROUP_NAME"] for u in out] == ["closers", "most-used"]
    assert out[0]["is_best_net_unit"] is True
    assert out[1]["is_best_net_unit"] is False
    for u in out:
        assert set(u) == {"GROUP_NAME", "EST_MIN", "GP", "poss",
                          "OFF_RATING", "DEF_RATING", "NET_RATING",
                          "PLUS_MINUS", "is_best_net_unit", "flags"}


def test_assemble_report_keys_and_math():
    players = _fifteen()
    units = [_unit("most-used", 500, 2.0, best=False),
             _unit("closers", 300, 10.0, best=True)]
    clutch = [{"PLAYER_NAME": "P1", "PLAYER_ID": 100, "GP": 10,
               "W": 6, "L": 4, "MIN": 30}]
    res = _assemble_rotation_report(team_id=14, abbrev="LAL",
                                    season="2025-26", min_possessions=100,
                                    top_units=5, players=players,
                                    units=units, clutch_rows=clutch)
    assert res["tool"] == "get_rotation_check"
    assert res["ok"] is True
    rows = res["rows"]
    for key in ("team", "coverage", "tiers", "starter_bench_split",
                "most_used_unit", "closing_candidates", "thin_flags",
                "clutch_context"):
        assert key in rows
    assert rows["team"] == {"id": 14, "abbrev": "LAL"}
    total = sum(p["MIN"] for p in players)
    core = sum(p["MIN"] for p in players[:5])
    assert rows["starter_bench_split"]["starter_min_share"] == round(core / total, 3)
    assert rows["most_used_unit"]["GROUP_NAME"] == "most-used"
    assert rows["closing_candidates"][0]["GROUP_NAME"] == "closers"
    assert "poss/2" in rows["coverage"]["minutes_basis"]
    assert "silver_clutch is player-scope only" in rows["clutch_context"]["note"]
    assert rows["clutch_context"]["closers"][0]["PLAYER"] == "P1"
    assert res["meta"]["source"] == "warehouse"
    assert res["meta"]["sample_floor"] == "100 possessions"
    assert "EST_MIN" in res["meta"]["data_note"]
    for p in rows["tiers"]["core"]:
        assert set(p) == {"PLAYER", "PLAYER_ID", "GP", "MIN", "MPG",
                          "PTS", "ON", "OFF", "DIFF", "CACHED"}


def test_assemble_empty_clutch_note():
    res = _assemble_rotation_report(team_id=14, abbrev="LAL",
                                    season="2025-26", min_possessions=100,
                                    top_units=5, players=_fifteen(),
                                    units=[_unit("u", 200, 1.0)],
                                    clutch_rows=[])
    assert "no cached clutch minutes" in res["rows"]["clutch_context"]["note"]
    assert res["rows"]["clutch_context"]["closers"] == []


def test_registered_in_tool_registry():
    assert "get_rotation_check" in tools.TOOL_NAMES


def test_invalid_team_fails_cleanly():
    res = _asyncio.run(get_rotation_check.ainvoke({"team": "Not A Real Team XYZ"}))
    assert res["ok"] is False
    assert "error" in res


def test_tool_hermetic_with_monkeypatched_fetchers(monkeypatch):
    raw = [{"player_id": 100 + i, "player_name": f"P{i + 1}", "gp": 60,
            "min": 36 - i, "pts": 24 - i} for i in range(12)]
    units = [_unit("most-used", 500, 2.0, best=False),
             _unit("closers", 300, 10.0, best=True)]
    clutch = [{"PLAYER_NAME": "P1", "PLAYER_ID": 100, "GP": 10,
               "W": 6, "L": 4, "MIN": 30}]

    async def _units(*a, **k):
        return units

    monkeypatch.setattr("app.tools.team.coerce_team_id", lambda t: 14)
    monkeypatch.setattr("app.tools.team._abbrev", lambda t: "LAL")
    monkeypatch.setattr("app.tools.team._fetch_rotation_players",
                        lambda *a, **k: raw)
    monkeypatch.setattr("app.tools.team._fetch_rotation_onoff",
                        lambda *a, **k: (110.0, 108.0, 2.0, True))
    monkeypatch.setattr("app.tools.team._fetch_rotation_units", _units)
    monkeypatch.setattr("app.tools.team._fetch_rotation_clutch",
                        lambda *a, **k: clutch)
    res = _asyncio.run(get_rotation_check.ainvoke({"team": "LAL"}))
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["team"] == {"id": 14, "abbrev": "LAL"}
    assert len(rows["tiers"]["core"]) == 5
    assert len(rows["tiers"]["bench"]) == 5
    assert rows["most_used_unit"]["GROUP_NAME"] == "most-used"
    assert rows["closing_candidates"][0]["GROUP_NAME"] == "closers"
    assert isinstance(rows["thin_flags"], list)
    assert res["meta"]["source"] == "warehouse"
