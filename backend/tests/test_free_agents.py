import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import seed_free_agents as sf
from scripts import vendor_cap as vc
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


def test_official_2026_27_constants():
    expected = {"cap": 164_961_000, "tax": 200_428_000,
                "apron1": 209_015_000, "apron2": 221_686_000}
    assert sf.CAP_2026_27 == expected
    assert vc.THRESHOLDS == {"season": "2026-27", **expected}
    assert sf.EXCEPTIONS_2026_27 == {
        "ntmle": 15_044_000, "tmle": 6_064_000,
        "room": 9_366_000, "bae": 5_477_000}


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
    cap = int(sf.CAP_2026_27["cap"] * sf.CAP_GROWTH)
    expected_room = cap - 21_000_000 - 16_000_000 - 13 * sf.MIN_SALARY
    assert row["PROJECTED_ROOM"] == expected_room
    assert row["MAX_ROOM"] == cap - 21_000_000 - 14 * sf.MIN_SALARY
    assert row["PROJECTED_ROOM"] < row["MAX_ROOM"]
    assert row["NTMLE_EST"] == 16_548_400
    assert row["TMLE_EST"] == 6_670_400
    assert row["BAE_EST"] == 6_024_700
    assert row["ROOM_EST"] == 10_302_600
    assert row["ESTIMATED"] is True


def test_implausible_room_flag():
    frame = pl.DataFrame({
        "PLAYER_NAME": [f"P{i}" for i in range(5)] + [f"O{i}" for i in range(5)],
        "TEAM": ["BOS"] * 10,
        "BREF_SLUG": [f"p{i}" for i in range(5)] + [f"o{i}" for i in range(5)],
        "SALARY_2026_27": [15_000_000] * 5 + [20_000_000] * 5,
        "SALARY_2027_28": [15_000_000] * 5 + [20_000_000] * 5,
        "OPTION_2027_28": [None] * 5 + ["player"] * 3 + ["team"] * 2,
    })
    _, room = sf.build_frames(frame, "2026_27", "2027_28")
    row = room.to_dicts()[0]
    assert row["PENDING_OPTION_SALARY"] == 100_000_000
    assert row["PROJECTED_ROOM"] <= 0.10 * row["PROJECTED_CAP"]
    assert row["PROJECTED_ROOM"] < row["MAX_ROOM"]


def test_tool_on_scratch(scratch):
    fa, room = sf.build_frames(_contracts(), "2026_27", "2027_28")
    store.save_frame("silver_free_agents", _result(fa), entity="league")
    store.save_frame("silver_cap_room", _result(room), entity="league")
    res = get_free_agents.func(team="BOS")
    assert res["ok"]
    assert len(res["free_agents"]) == 2
    assert res["cap_room"][0]["TEAM"] == "BOS"
    assert res["cap_room"][0]["TMLE_EST"] == 6_670_400
    assert res["meta"]["estimated"] is True
    league = get_free_agents.func(team="")
    assert league["ok"]
    assert len(league["free_agents"]) == 2


def test_tool_accepts_cap_room_without_tmle(scratch):
    fa, room = sf.build_frames(_contracts(), "2026_27", "2027_28")
    store.save_frame("silver_free_agents", _result(fa), entity="league")
    store.save_frame("silver_cap_room", _result(room.drop("TMLE_EST")),
                     entity="league")
    res = get_free_agents.func(team="BOS")
    assert res["ok"]
    assert res["cap_room"][0]["TEAM"] == "BOS"
    assert "TMLE_EST" not in res["cap_room"][0]


def test_tool_filters_cap_room_by_mapped_cap_season(scratch):
    fa, room = sf.build_frames(_contracts(), "2026_27", "2027_28")
    future_room = room.with_columns([
        pl.lit("2028-29").alias("CAP_SEASON"),
        pl.lit(20_000_000).cast(pl.Int64).alias("COMMITTED_SALARY"),
    ])
    store.save_frame("silver_free_agents", _result(fa), entity="league")
    store.save_frame("silver_cap_room", _result(pl.concat([room, future_room])),
                     entity="league")
    current = get_free_agents.func(team="BOS", fa_year="2027")
    assert current["ok"]
    assert current["cap_season"] == "2027-28"
    assert len(current["cap_room"]) == 1
    assert current["cap_room"][0]["CAP_SEASON"] == "2027-28"
    assert current["cap_room"][0]["COMMITTED_SALARY"] == 21_000_000
    league = get_free_agents.func(team="", fa_year="2027")
    assert len(league["cap_room"]) == 1
    future = get_free_agents.func(team="BOS", fa_year="2028")
    assert future["ok"]
    assert future["cap_season"] == "2028-29"
    assert len(future["cap_room"]) == 1
    assert future["cap_room"][0]["CAP_SEASON"] == "2028-29"
    assert future["cap_room"][0]["COMMITTED_SALARY"] == 20_000_000


def test_tool_rejects_invalid_fa_year(scratch):
    res = get_free_agents.func(team="BOS", fa_year="2027-28")
    assert res["ok"] is False
    assert "four-digit calendar year" in res["error"]


def test_tool_missing(scratch):
    res = get_free_agents.func(team="BOS")
    assert res["ok"] is False
    assert "seed_free_agents" in res["error"]
