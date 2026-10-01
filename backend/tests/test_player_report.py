import asyncio
import datetime as dt
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import duckdb
import pytest
from app import graph
from shared import store
from shared.tools import TOOL_NAMES, get_player_report
from shared.tools import _core as core_mod
from v2.adapters import coverage as coverage_mod


@pytest.fixture()
def warehouse(monkeypatch, tmp_path):
    path = tmp_path / "playerreport.duckdb"
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE silver_boxscores (_season VARCHAR, GAME_ID VARCHAR)"
        )
        for start in range(2015, 2025):
            season = f"{start}-{str(start + 1)[2:]}"
            connection.execute(
                "INSERT INTO silver_boxscores VALUES (?, ?)",
                [season, "002" + str(start) + "00001"],
            )
    finally:
        connection.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store._tables_cache.clear()
    store._pool_evict_all()
    store.warehouse_identity_cache_clear()
    core_mod.last_completed_season_cache_clear()
    coverage_mod.coverage_cache_clear()
    yield path
    core_mod.last_completed_season_cache_clear()
    coverage_mod.coverage_cache_clear()


def _drain(q):
    async def go():
        st={"question":q,"history":[],"tool_results":[],"calls_made":[],"round":0}
        async for _ in graph._triage_seed(q,"primary","model",st): pass
        return st
    return asyncio.run(go())


def test_registered(): assert "get_player_report" in TOOL_NAMES

def test_lebron_report_has_all_four_parts():
    o=get_player_report.invoke({"player":"LeBron James"})
    assert o["ok"]
    assert set(o["rows"]) == {"season_line","advanced","shot_profile","clutch"}
    assert len(o["rows"]["shot_profile"]) >= 5
    assert o["rows"]["clutch"]["PTS"] > 0
    text=o["meta"]["deterministic_answer"]
    for x in ("20.9 PPG","59.4% true shooting","Restricted Area","Clutch:"):
        assert x in text

def test_compound_route_beats_first_matching_average_lane():
    st=_drain("For LeBron this season, give me his averages, advanced metrics, shot profile, and clutch scoring.")
    assert [x.split(":",1)[0] for x in st["calls_made"]] == ["get_player_report"]

def test_this_season_average_resolves_to_calendar_refusal(warehouse):
    expected = core_mod.completed_season_for_date(dt.date.today())
    assert expected != "2024-25"
    st = _drain("What did LeBron average this season?")
    names = [x.split(":", 1)[0] for x in st["calls_made"]]
    assert "get_season_averages" in names
    sent = []
    for entry in st["calls_made"]:
        _name, _, blob = entry.partition(":")
        try:
            args = json.loads(blob)
        except Exception:
            continue
        if isinstance(args, dict) and args.get("season"):
            sent.append(args["season"])
    assert sent
    assert all(season == expected for season in sent)
    assert all(season != "2024-25" for season in sent)
    refusals = [result for result in st["tool_results"]
                if result.get("season_error") is True]
    assert refusals
    assert all(expected in str(result.get("error") or "")
               for result in refusals)

def test_historical_report_stays_warehouse_bounded(monkeypatch):
    from shared.tools import player as module
    line = {"PLAYER_ID": 1, "PLAYER": "Test Player", "GP": 70,
            "PPG": 20.0, "RPG": 5.0, "APG": 6.0, "TS_PCT": .617}
    class Fake:
        def __init__(self, result=None): self.result = result
        def invoke(self, _):
            if self.result is None: raise AssertionError("live enrichment")
            return self.result
    monkeypatch.setattr(module, "coerce_player_id", lambda _: 1)
    monkeypatch.setattr(module, "get_season_averages",
                        Fake({"ok": True, "rows": [line]}))
    monkeypatch.setattr(module, "get_advanced", Fake())
    monkeypatch.setattr(module, "get_shot_zones", Fake())
    import shared.tools.league as league
    monkeypatch.setattr(league, "get_clutch", Fake())
    out = module.get_player_report.invoke({"player": "Test Player", "season": "2023-24"})
    assert out["ok"]
    assert out["rows"]["advanced"] is None
    assert "61.7% true shooting" in out["meta"]["deterministic_answer"]
