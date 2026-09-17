"""Multi-part player asks should answer every requested dimension."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import graph
from app.tools import TOOL_NAMES, get_player_report


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

def test_simple_average_stays_simple():
    st=_drain("What did LeBron average this season?")
    assert [x.split(":",1)[0] for x in st["calls_made"]] == ["get_season_averages"]

def test_historical_report_stays_warehouse_bounded(monkeypatch):
    from app.tools import player as module
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
    import app.tools.league as league
    monkeypatch.setattr(league, "get_clutch", Fake())
    out = module.get_player_report.invoke({"player": "Test Player", "season": "2023-24"})
    assert out["ok"]
    assert out["rows"]["advanced"] is None
    assert "61.7% true shooting" in out["meta"]["deterministic_answer"]
