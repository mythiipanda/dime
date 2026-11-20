import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
import polars as pl
import pytest

from shared import store
from shared.tools import player as pm

SEASON = "2009-10"
PID = "999001"

GAMELOG_DDL = """
    CREATE TABLE silver_player_gamelogs (
        _season TEXT,
        _entity TEXT,
        PTS DOUBLE,
        REB DOUBLE,
        AST DOUBLE,
        STL DOUBLE,
        BLK DOUBLE,
        MIN DOUBLE,
        TOV DOUBLE,
        FGM DOUBLE,
        FGA DOUBLE,
        FG3M DOUBLE,
        FG3A DOUBLE,
        FTM DOUBLE,
        FTA DOUBLE,
        GAME_DATE TEXT,
        MATCHUP TEXT,
        TEAM_ABBREVIATION TEXT
    )
"""

SEASON_DDL = """
    CREATE TABLE silver_player_season (
        _season TEXT,
        PLAYER_ID INTEGER,
        PLAYER TEXT,
        TEAM TEXT,
        GP INTEGER,
        MPG DOUBLE,
        PPG DOUBLE,
        RPG DOUBLE,
        APG DOUBLE,
        SPG DOUBLE,
        BPG DOUBLE,
        FG_PCT DOUBLE,
        FG3_PCT DOUBLE,
        FT_PCT DOUBLE,
        TS_PCT DOUBLE
    )
"""

SEASON_ROW = (
    SEASON,
    999001,
    "Fixture Wonder",
    "FIX",
    82,
    36.0,
    25.3,
    7.1,
    6.2,
    1.1,
    0.4,
    0.46,
    0.40,
    0.85,
    0.58,
)

GAMELOG_ROW_ZERO = (SEASON, f"player:{PID}", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "2009-11-03", "FIX vs. BOS", "FIX")
GAMELOG_ROW_PTS28 = (SEASON, f"player:{PID}", 28.0, 5.0, 4.0, 1.0, 0.0, 37.0, 2.0, 10.0, 21.0, 2.0, 5.0, 6.0, 7.0, "2009-11-05", "FIX @ NYK", "FIX")


class _EmptyStub:
    def __init__(self):
        self.calls = []

    async def ainvoke(self, args):
        self.calls.append(args)
        return {"ok": True, "rows": []}


class _EmptyDictStub:
    def __init__(self):
        self.calls = []

    async def ainvoke(self, args):
        self.calls.append(args)
        return {"ok": True, "rows": {}}


class _IntelGamelogStub:
    def __init__(self):
        self.calls = []

    async def ainvoke(self, args):
        self.calls.append(args)
        return {
            "ok": True,
            "rows": [
                {
                    "MATCHUP": "FIX vs. BOS",
                    "PTS": 10.0,
                    "REB": 2.0,
                    "AST": 3.0,
                    "FGA": 8.0,
                    "FGM": 4.0,
                    "FG3A": 2.0,
                    "FG3M": 1.0,
                    "FTA": 2.0,
                    "FTM": 1.0,
                    "MIN": 20.0,
                    "STL": 0.0,
                    "BLK": 0.0,
                    "TOV": 1.0,
                }
            ],
            "meta": {"source": "warehouse"},
        }


def _patch_no_live(monkeypatch):
    import nba_api.stats.endpoints as _ep

    calls = []

    class _NoLive:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("live HTTP touched")

    monkeypatch.setattr(_ep, "CommonPlayerInfo", _NoLive)
    return calls


@pytest.fixture
def synth(monkeypatch, tmp_path):
    wh = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(wh))
    con.execute(GAMELOG_DDL)
    con.execute(SEASON_DDL)
    con.execute(
        "INSERT INTO silver_player_season VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        SEASON_ROW,
    )
    con.close()

    monkeypatch.setattr(store, "DB_PATH", wh)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    monkeypatch.setattr(store, "connect", lambda **_kw: duckdb.connect(str(wh)))

    def _fake_read_frame(table, where="", params=None):
        if table == "silver_player_season":
            return pl.DataFrame({
                "_season": [SEASON],
                "PLAYER_ID": [999001],
                "PLAYER": ["Fixture Wonder"],
                "TEAM": ["FIX"],
                "GP": [82],
                "MPG": [36.0],
                "PPG": [25.3],
                "RPG": [7.1],
                "APG": [6.2],
                "SPG": [1.1],
                "BPG": [0.4],
                "FG_PCT": [0.46],
                "FG3_PCT": [0.40],
                "FT_PCT": [0.85],
                "TS_PCT": [0.58],
            })
        raise store.TableAbsent(table, str(wh))

    monkeypatch.setattr(store, "read_frame", _fake_read_frame)
    _patch_no_live(monkeypatch)
    for name, cls in (("get_last_x", _EmptyStub), ("get_advanced", _EmptyDictStub), ("get_shot_zones", _EmptyStub)):
        monkeypatch.setattr(pm, name, cls())
    return wh


def _seed_gamelogs(wh, rows):
    con = duckdb.connect(str(wh))
    for row in rows:
        con.execute(
            "INSERT INTO silver_player_gamelogs (_season, _entity, PTS, REB, AST, STL, BLK, MIN, TOV, FGM, FGA, FG3M, FG3A, FTM, FTA, GAME_DATE, MATCHUP, TEAM_ABBREVIATION) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            row,
        )
    con.close()


def test_season_line_intel_is_not_a_game(synth):
    result = asyncio.run(pm._compare_one(PID, SEASON))
    assert result.get("missing_population") is True
    assert result.get("missing") == ["season_game_logs"]
    assert "ppg" not in result
    assert result.get("sub_call_errors")=={}


def test_zero_valued_warehouse_games_preserved(synth):
    _seed_gamelogs(synth, [GAMELOG_ROW_ZERO, GAMELOG_ROW_PTS28])
    result = asyncio.run(pm._compare_one(PID, SEASON))
    assert result.get("gp") == 2
    assert result.get("ppg") == pytest.approx(14.0)
    assert result.get("missing_population") is not True


def test_intel_gamelog_fallback_without_season_line_coverage_still_counts(synth, monkeypatch):
    monkeypatch.setattr(pm, "get_player_intel", _IntelGamelogStub())
    result = asyncio.run(pm._compare_one(PID, SEASON))
    assert result.get("gp") == 1
    assert result.get("ppg") == pytest.approx(10.0)
    assert result.get("missing_population") is not True


def test_standalone_get_player_intel_season_line_unchanged(synth):
    result = asyncio.run(pm.get_player_intel.ainvoke({"player_id": PID, "season": SEASON}))
    assert result.get("ok") is True
    rows = result.get("rows") or []
    assert rows, "expected the synthetic season-line row"
    assert rows[0].get("GP") == 82
    assert rows[0].get("PPG") == pytest.approx(25.3)
    assert (result.get("meta") or {}).get("coverage") == "season_line"
