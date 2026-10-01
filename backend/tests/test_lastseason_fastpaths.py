import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _triage_seed
from shared import store
from shared.tools import _core as core_mod
from v2.adapters import coverage as coverage_mod

WAREHOUSE_SEASONS = [
    "2015-16",
    "2016-17",
    "2017-18",
    "2018-19",
    "2019-20",
    "2020-21",
    "2021-22",
    "2022-23",
    "2023-24",
    "2024-25",
]

WAREHOUSE_MAX = "2024-25"

RATINGS_ROWS = [
    (14, "Los Angeles Lakers", 82, 50, 32, 115.2, 113.1, 2.1),
    (2, "Boston Celtics", 82, 59, 23, 120.1, 110.3, 9.8),
]


def _seed(path):
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE silver_team_ratings ("
            "TEAM_ID INTEGER, TEAM_NAME VARCHAR, GP INTEGER, "
            "W INTEGER, L INTEGER, OFF_RATING DOUBLE, DEF_RATING DOUBLE, "
            "NET_RATING DOUBLE, PACE DOUBLE, TS_PCT DOUBLE, "
            "TM_TOV_PCT DOUBLE, _season VARCHAR, _source VARCHAR, "
            "_fetched_at VARCHAR)"
        )
        for tid, name, gp, w, l, off, dfn, net in RATINGS_ROWS:
            connection.execute(
                "INSERT INTO silver_team_ratings VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [tid, name, gp, w, l, off, dfn, net,
                 99.0, 0.585, 12.0, WAREHOUSE_MAX, "seed", "2024-01-01"],
            )
        connection.execute(
            "CREATE TABLE silver_boxscores (_season VARCHAR, GAME_ID VARCHAR)"
        )
        for season in WAREHOUSE_SEASONS:
            connection.execute(
                "INSERT INTO silver_boxscores VALUES (?, ?)",
                [season, "002" + season[:4] + "00001"],
            )
    finally:
        connection.close()


@pytest.fixture()
def warehouse(monkeypatch, tmp_path):
    path = tmp_path / "fastpaths.duckdb"
    _seed(path)
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


def _calendar_season():
    season = core_mod.completed_season_for_date(dt.date.today())
    if season == WAREHOUSE_MAX:
        pytest.skip("calendar season coincides with fixture max")
    return season


def _drive(question):
    state = {
        "question": question,
        "history": [],
        "tool_results": [],
        "calls_made": [],
    }

    async def _collect():
        async for _event in _triage_seed(question, "primary", "model", state):
            pass

    asyncio.run(_collect())
    return state


def _tool_seasons(state):
    found = []
    for entry in state["calls_made"]:
        name, _, blob = entry.partition(":")
        try:
            args = json.loads(blob)
        except Exception:
            continue
        if isinstance(args, dict) and args.get("season"):
            found.append((name, args["season"]))
    return found


def _assert_calendar_season_no_substitution(state, tool):
    expected = _calendar_season()
    seasons = _tool_seasons(state)
    assert seasons, f"{tool}: no tool call recorded a season"
    for name, season in seasons:
        assert season == expected, f"{tool}: {name} sent {season}"
    dumped = json.dumps(state["calls_made"], sort_keys=True)
    assert WAREHOUSE_MAX not in dumped, (
        f"{tool}: warehouse max leaked into calls")
    refusals = [result for result in state["tool_results"]
                if result.get("season_error") is True]
    assert refusals, f"{tool}: no coverage refusal recorded"
    for result in refusals:
        assert expected in str(result.get("error") or ""), (
            f"{tool}: refusal names no season")


def _assert_warehouse_default(state, tool):
    seasons = _tool_seasons(state)
    assert seasons, f"{tool}: no tool call recorded a season"
    for name, season in seasons:
        assert season == WAREHOUSE_MAX, f"{tool}: {name} sent {season}"


def _call_names(state):
    return [entry.partition(":")[0] for entry in state["calls_made"]]


def test_leaders_send_calendar_season(warehouse):
    state = _drive("Which player leads the league in assists last season?")
    names = [name for name, _ in _tool_seasons(state)]
    assert "get_leaders" in names
    _assert_calendar_season_no_substitution(state, "get_leaders")


def test_single_team_ratings_send_calendar_season(warehouse):
    state = _drive("What is the Lakers net rating last season?")
    names = _call_names(state)
    assert "get_ratings" in names
    _assert_calendar_season_no_substitution(state, "get_ratings")


def test_two_team_compare_sends_calendar_season(warehouse):
    state = _drive("Compare the Lakers and Celtics net ratings last season")
    names = _call_names(state)
    assert "get_ratings" in names
    _assert_calendar_season_no_substitution(state, "two-team get_ratings")


def test_clutch_sends_calendar_season(warehouse):
    state = _drive("Who are the top clutch scorers last season?")
    names = [name for name, _ in _tool_seasons(state)]
    assert "get_clutch" in names
    _assert_calendar_season_no_substitution(state, "get_clutch")


def test_team_compare_without_season_keeps_warehouse_default(warehouse):
    state = _drive(
        "Top 5 teams in scoring totals with per game averages and wins?")
    names = [name for name, _ in _tool_seasons(state)]
    assert "get_team_compare" in names
    _assert_warehouse_default(state, "get_team_compare")


def test_rest_sends_calendar_season(warehouse):
    state = _drive("Which team has the biggest rest advantage last season?")
    names = [name for name, _ in _tool_seasons(state)]
    assert "get_rest" in names
    _assert_calendar_season_no_substitution(state, "get_rest")


def test_playoff_sim_sends_calendar_season(warehouse):
    state = _drive("What are the championship odds last season?")
    names = [name for name, _ in _tool_seasons(state)]
    assert "get_playoff_sim" in names
    _assert_calendar_season_no_substitution(state, "get_playoff_sim")


def test_trade_check_without_season_keeps_warehouse_default(warehouse):
    state = _drive(
        "Grade the trade: Anthony Davis for Jayson Tatum, "
        "Lakers and Celtics?")
    seasons = _tool_seasons(state)
    assert ("get_trade_check", WAREHOUSE_MAX) in seasons
    dumped = json.dumps(state["calls_made"], sort_keys=True)
    assert _calendar_season() not in dumped


def test_contract_value_sends_calendar_season(warehouse):
    state = _drive("Who is the most overpaid player last season?")
    names = [name for name, _ in _tool_seasons(state)]
    assert "get_contract_value" in names
    _assert_calendar_season_no_substitution(state, "get_contract_value")


def test_explicit_season_slug_still_wins(warehouse):
    state = _drive("Compare the Lakers and Celtics net ratings in 2023-24")
    seasons = _tool_seasons(state)
    assert seasons
    for _name, season in seasons:
        assert season == "2023-24"
