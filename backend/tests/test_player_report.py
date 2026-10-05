import datetime as dt
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import duckdb
import pytest
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


def test_registered(): assert "get_player_report" in TOOL_NAMES

def test_lebron_report_names_the_absent_season_table():
    pytest = __import__("pytest")
    with pytest.raises(store.TableAbsent) as info:
        get_player_report.invoke({"player": "LeBron James"})
    assert info.value.table == "silver_player_season"
    assert str(store.DB_PATH) == info.value.warehouse
    assert store.DB_PATH.name in str(info.value)

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
