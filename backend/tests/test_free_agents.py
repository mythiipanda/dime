import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import seed_free_agents as sf
from shared import store
from shared.sources.base import FetchMeta, FetchResult
from shared.tools.league.free_agents import get_free_agents


def _result(frame, source="derived:bref_contracts", season="2026-27"):
    return FetchResult(frame=frame, meta=FetchMeta(source=source,
                                                 season=season))


@pytest.fixture()
def scratch(tmp_path):
    db = tmp_path / "wh.duckdb"
    old_db, old_lock = store.DB_PATH, store.LOCK_PATH
    store.DB_PATH = db
    store.LOCK_PATH = tmp_path / ".write.lock"
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    yield db
    store.DB_PATH, store.LOCK_PATH = old_db, old_lock
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()


def _contracts():
    return pl.DataFrame({
        "PLAYER_NAME": ["Signed Vet", "Option Guy", "Expiring Man"],
        "TEAM": ["BOS", "BOS", "BOS"],
        "BREF_SLUG": ["vet01", "opt01", "exp01"],
        "SALARY_2026_27": [20_000_000, 15_000_000, 10_000_000],
        "SALARY_2027_28": [21_000_000, 16_000_000, None],
        "SALARY_2028_29": [22_000_000, None, None],
        "OPTION_2027_28": [None, "player", None],
        "OPTION_2028_29": [None, None, None],
        "GUARANTEED": [43_000_000, 15_000_000, 10_000_000],
    })


def test_build_frames():
    fa, room = sf.build_frames(_contracts(), "2026_27", "2027_28")
    types = {r["PLAYER_NAME"]: r["FA_TYPE"] for r in fa.to_dicts()}
    assert types == {"Option Guy": "player_option",
                     "Expiring Man": "ufa"}
    row = room.to_dicts()[0]
    assert row["TEAM"] == "BOS"
    assert row["COMMITTED_SALARY"] == 21_000_000
    assert row["PENDING_OPTION_SALARY"] == 16_000_000
    assert row["PLAYERS_UNDER_CONTRACT"] == 2
    assert row["PENDING_OPTIONS"] == 1
    expected_room = int(sf.CAP_2026_27["cap"] * sf.CAP_GROWTH) \
        - 21_000_000 - 12 * sf.MIN_SALARY
    assert row["PROJECTED_ROOM"] == expected_room
    assert row["ESTIMATED"] is True


def test_tool_on_scratch(scratch):
    fa, room = sf.build_frames(_contracts(), "2026_27", "2027_28")
    store.save_frame("silver_free_agents", _result(fa), entity="league")
    store.save_frame("silver_cap_room", _result(room), entity="league")
    res = get_free_agents.func(team="BOS")
    assert res["ok"]
    assert len(res["free_agents"]) == 2
    assert res["cap_room"][0]["TEAM"] == "BOS"
    assert res["meta"]["estimated"] is True
    league = get_free_agents.func(team="")
    assert league["ok"]
    assert len(league["free_agents"]) == 2


def test_tool_missing(scratch):
    res = get_free_agents.func(team="BOS")
    assert res["ok"] is False
    assert "seed_free_agents" in res["error"]
