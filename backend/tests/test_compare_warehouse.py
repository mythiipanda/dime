"""Compare warehouse-hit vs live-fallback (hermetic where applicable)."""

import asyncio
import sys
from collections import Counter
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store
from app.tools import player as pm

SEASON = "2025-26"
EDWARDS = 1630162
LUKA = 1629029

ZONE_ROWS = [
    {"zone": "Restricted Area", "SHARE": 0.22},
    {"zone": "Above the Break 3", "SHARE": 0.42},
]

EDWARDS_ON = 118.5
EDWARDS_OFF = 112.3


class _ZoneStub:
    async def ainvoke(self, args):
        return {"ok": True, "rows": [dict(r) for r in ZONE_ROWS]}


class _EmptyStub:
    def __init__(self):
        self.calls = []

    async def ainvoke(self, args):
        self.calls.append(dict(args))
        return {"ok": True, "rows": []}


def _seed_warehouse(wh: Path):
    con = duckdb.connect(str(wh))
    try:
        con.execute(
            "CREATE TABLE silver_player_gamelogs ("
            "_season TEXT, _entity TEXT, PTS DOUBLE, REB DOUBLE, AST DOUBLE, "
            "STL DOUBLE, BLK DOUBLE, MIN DOUBLE, TOV DOUBLE, FGM DOUBLE, "
            "FGA DOUBLE, FG3M DOUBLE, FG3A DOUBLE, FTM DOUBLE, FTA DOUBLE, "
            "GAME_DATE TEXT, MATCHUP TEXT, TEAM_ABBREVIATION TEXT)"
        )
        gamelogs = [
            (EDWARDS, "MIN vs. BOS", "MIN"),
            (LUKA, "LAL vs. BOS", "LAL"),
        ]
        dates = ["Oct 22, 2025", "Oct 24, 2025", "Oct 26, 2025"]
        for pid, matchup, abbr in gamelogs:
            for i, gd in enumerate(dates):
                con.execute(
                    "INSERT INTO silver_player_gamelogs VALUES "
                    "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        SEASON, f"player:{pid}",
                        28 + i, 6, 5, 1, 1, 35.0, 3, 10, 20, 3, 8, 5, 6,
                        gd, matchup, abbr,
                    ],
                )
        con.execute(
            'CREATE TABLE silver_on_off ('
            '_season TEXT, _entity TEXT, Stat TEXT, "On" DOUBLE, "Off" DOUBLE)'
        )
        con.execute(
            "INSERT INTO silver_on_off VALUES (?, ?, ?, ?, ?)",
            [SEASON, f"player:{EDWARDS}", "Pts per 100 Possessions",
             EDWARDS_ON, EDWARDS_OFF],
        )
        con.execute(
            "INSERT INTO silver_on_off VALUES (?, ?, ?, ?, ?)",
            [SEASON, f"player:{LUKA}", "Pts per 100 Possessions", 120.1, 114.0],
        )
        con.execute(
            "CREATE TABLE silver_advanced ("
            "PLAYER_ID INTEGER, TEAM_ABBREVIATION TEXT, USG_PCT DOUBLE, "
            "TM_TOV_PCT DOUBLE, PIE DOUBLE, _season TEXT)"
        )
        con.execute(
            "INSERT INTO silver_advanced VALUES (?, ?, ?, ?, ?, ?)",
            [EDWARDS, "MIN", 0.31, 9.5, 0.15, SEASON],
        )
        con.execute(
            "INSERT INTO silver_advanced VALUES (?, ?, ?, ?, ?, ?)",
            [LUKA, "LAL", 0.32, 10.1, 0.16, SEASON],
        )
        con.execute(
            "CREATE TABLE silver_standings ("
            "TeamName TEXT, WINS INTEGER, LOSSES INTEGER, _season TEXT)"
        )
        con.execute(
            "INSERT INTO silver_standings VALUES (?, ?, ?, ?)",
            ["Timberwolves", 49, 33, SEASON],
        )
        con.execute(
            "INSERT INTO silver_standings VALUES (?, ?, ?, ?)",
            ["Lakers", 50, 32, SEASON],
        )
        con.execute(
            "CREATE TABLE silver_rapm ("
            "player_id INTEGER, rapm DOUBLE, _season TEXT)"
        )
        con.execute(
            "INSERT INTO silver_rapm VALUES (?, ?, ?)", [EDWARDS, 2.5, SEASON]
        )
        con.execute(
            "INSERT INTO silver_rapm VALUES (?, ?, ?)", [LUKA, 3.1, SEASON]
        )
        con.execute(
            "CREATE TABLE silver_clutch ("
            "PLAYER_NAME TEXT, PTS INTEGER, _season TEXT)"
        )
        con.execute(
            "INSERT INTO silver_clutch VALUES (?, ?, ?)",
            ["Anthony Edwards", 135, SEASON],
        )
        con.execute(
            "INSERT INTO silver_clutch VALUES (?, ?, ?)",
            ["Luka Doncic", 120, SEASON],
        )
        con.execute(
            "INSERT INTO silver_clutch VALUES (?, ?, ?)",
            ["Luka Don\u010di\u0107", 120, SEASON],
        )
    finally:
        con.close()


@pytest.fixture()
def warehouse(monkeypatch, tmp_path):
    wh = tmp_path / "wh.duckdb"
    _seed_warehouse(wh)
    monkeypatch.setattr(store, "connect",
                        lambda **_kw: duckdb.connect(str(wh)))
    return wh


class _EmptyDictStub:
    async def ainvoke(self, args):
        return {"ok": True, "rows": {}}


class _IntelStub:
    async def ainvoke(self, args):
        if int(args.get("player_id", 0)) == 1628983:
            return {"ok": True, "rows": []}
        return {"ok": True, "rows": []}


def _patch_no_live(monkeypatch):
    import nba_api.stats.endpoints as _ep
    calls = []
    class _NoLive:
        def __init__(self, *a, **k):
            calls.append(k)
            raise AssertionError("live HTTP touched")
    monkeypatch.setattr(_ep, "CommonPlayerInfo", _NoLive)
    return calls


def test_warehouse_hit_makes_zero_live_calls(warehouse, monkeypatch):
    calls = _patch_no_live(monkeypatch)
    monkeypatch.setattr(pm, "get_shot_zones", _ZoneStub())
    result = asyncio.run(pm.get_compare.ainvoke(
        {"a": "1630162", "b": "1629029", "season": SEASON}))
    assert result["ok"] is True
    rows = result["rows"]
    assert rows["a"]["team"] == "MIN"
    assert rows["b"]["team"] == "LAL"
    assert rows["a"]["net_onoff"] == round(EDWARDS_ON - EDWARDS_OFF, 1)
    assert calls == []


def test_warehouse_miss_falls_back_to_live(warehouse, monkeypatch):
    import pandas as pd

    import nba_api.stats.endpoints as _ep

    calls: list = []

    class _FakeInfo:
        def __init__(self, *a, **k):
            calls.append(k)
            self._k = k

        def get_data_frames(self):
            return [pd.DataFrame({"TEAM_ID": [1610612747]})]

    monkeypatch.setattr(_ep, "CommonPlayerInfo", _FakeInfo)
    monkeypatch.setattr(pm, "get_player_intel", _IntelStub())
    monkeypatch.setattr(pm, "get_last_x", _EmptyStub())
    monkeypatch.setattr(pm, "get_advanced", _EmptyDictStub())
    monkeypatch.setattr(pm, "get_shot_zones", _EmptyStub())
    onoff_rec = _EmptyStub()
    monkeypatch.setattr(pm, "get_on_off", onoff_rec)
    result = asyncio.run(pm.get_compare.ainvoke(
        {"a": "1628983", "b": "1630162", "season": SEASON}))
    assert result["ok"] is True
    mine = [c for c in calls if c.get("player_id") == 1628983]
    assert len(mine) == 1
    assert onoff_rec.calls
    assert onoff_rec.calls[0].get("team_id") == 1610612747


def test_real_warehouse_zero_live_calls(monkeypatch):
    calls = _patch_no_live(monkeypatch)
    monkeypatch.setattr(pm, "get_shot_zones", _ZoneStub())
    result = asyncio.run(pm.get_compare.ainvoke(
        {"a": "Anthony Edwards", "b": "Luka Doncic", "season": SEASON}))
    assert result["ok"] is True
    rows = result["rows"]
    assert rows["a"]["team"] == "MIN"
    assert rows["b"]["team"] == "LAL"
    assert rows["a"]["net_onoff"] is not None
    assert rows["a"]["gp"] > 50
    assert rows["a"]["team_record"] != ""
    con = duckdb.connect(str(store.DB_PATH), read_only=True)
    try:
        matchups = con.execute(
            "SELECT MATCHUP FROM silver_player_gamelogs"
            " WHERE _season = ? AND _entity = ?",
            [SEASON, f"player:{EDWARDS}"],
        ).fetchall()
    finally:
        con.close()
    first_tokens = [str(m[0] or "").split(" ")[0] for m in matchups if m[0]]
    expected = Counter(t for t in first_tokens if t).most_common(1)[0][0]
    assert rows["a"]["team"] == expected
    assert calls == []


def test_warehouse_team_ids_match_live_path(monkeypatch):
    """The warehouse-derived team ids must equal what the live fallback
    would return, so compare output is unchanged by the fast path."""
    import pandas as pd

    import nba_api.stats.endpoints as _ep
    from app.tools import _core as _core

    monkeypatch.setattr(pm, "get_shot_zones", _ZoneStub())
    monkeypatch.setattr(pm, "get_last_x", _EmptyStub())
    monkeypatch.setattr(pm, "get_advanced", _EmptyDictStub())
    monkeypatch.setattr(pm, "get_player_intel", _IntelStub())
    monkeypatch.setattr(pm, "get_on_off", _EmptyStub())

    real_coerce = _core.coerce_team_id
    fast_ids = {}

    def _record(value):
        tid = real_coerce(value)
        fast_ids[str(value)] = tid
        return tid

    monkeypatch.setattr(pm, "coerce_team_id", _record)
    monkeypatch.setattr(_core, "coerce_team_id", _record)

    class _NoLive:
        def __init__(self, *a, **k):
            raise AssertionError("live HTTP touched on fast path")

    monkeypatch.setattr(_ep, "CommonPlayerInfo", _NoLive)
    fast = asyncio.run(pm.get_compare.ainvoke(
        {"a": "Anthony Edwards", "b": "Luka Doncic", "season": SEASON}))
    assert fast["ok"] is True

    def _boom(_value):
        raise RuntimeError("force live fallback")
    monkeypatch.setattr(pm, "coerce_team_id", _boom)
    monkeypatch.setattr(_core, "coerce_team_id", _boom)

    TEAM_BY_PID = {1630162: 1610612750, 1629029: 1610612747}
    live_calls = []

    class _FakeInfo:
        def __init__(self, *a, **k):
            live_calls.append(k.get("player_id"))
            self._k = k

        def get_data_frames(self):
            return [pd.DataFrame(
                {"TEAM_ID": [TEAM_BY_PID[self._k.get("player_id")]]})]

    monkeypatch.setattr(_ep, "CommonPlayerInfo", _FakeInfo)
    live = asyncio.run(pm.get_compare.ainvoke(
        {"a": "Anthony Edwards", "b": "Luka Doncic", "season": SEASON}))
    assert live["ok"] is True

    assert set(live_calls) == {1630162, 1629029}
    assert fast_ids == {"MIN": 1610612750, "LAL": 1610612747}
    assert set(fast_ids.values()) == set(TEAM_BY_PID.values())
    assert fast["rows"] == live["rows"]
    assert fast["rows"]["a"]["team"] == "MIN"
    assert fast["rows"]["b"]["team"] == "LAL"


class _FlakyLastStub:
    """Fails once, then succeeds: a transient sub-call must be retried."""

    def __init__(self):
        self.calls = 0

    async def ainvoke(self, args):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient boom")
        return {"ok": True, "rows": [{"PTS": 30}, {"PTS": 28}]}


class _BoomStub:
    async def ainvoke(self, args):
        raise RuntimeError("boom")


def _patch_compare_stubs(monkeypatch, last_stub):
    monkeypatch.setattr(pm, "get_last_x", last_stub)
    monkeypatch.setattr(pm, "get_advanced", _EmptyDictStub())
    monkeypatch.setattr(pm, "get_shot_zones", _EmptyStub())


def test_last5_recovers_after_transient_failure(warehouse, monkeypatch):
    """Ticket 4: a once-failing get_last_x is retried, so last5 populates
    instead of silently coming back []."""
    _patch_no_live(monkeypatch)
    flaky = _FlakyLastStub()
    _patch_compare_stubs(monkeypatch, flaky)
    result = asyncio.run(pm.get_compare.ainvoke(
        {"a": "1630162", "b": "1629029", "season": SEASON}))
    assert result["ok"] is True
    assert result["rows"]["a"]["last5"] == [30, 28]
    assert result["meta"]["sub_call_errors"] == {}


def test_last5_failure_surfaced_in_meta(warehouse, monkeypatch):
    """Ticket 4: when a sub-call keeps failing, the failure is surfaced in
    meta instead of being swallowed into last5: []."""
    _patch_no_live(monkeypatch)
    _patch_compare_stubs(monkeypatch, _BoomStub())
    result = asyncio.run(pm.get_compare.ainvoke(
        {"a": "1630162", "b": "1629029", "season": SEASON}))
    assert result["ok"] is True
    assert result["rows"]["a"]["last5"] == []
    assert "a.last" in result["meta"]["sub_call_errors"]
    assert "RuntimeError" in result["meta"]["sub_call_errors"]["a.last"]
