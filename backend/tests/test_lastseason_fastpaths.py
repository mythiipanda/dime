import asyncio
import json
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _triage_seed
from shared import store
from shared.tools import _core as core_mod

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
                 99.0, 0.585, 12.0, "2024-25", "seed", "2024-01-01"],
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
    yield path
    core_mod.last_completed_season_cache_clear()


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


def _assert_derived_season(state, tool):
    seasons = _tool_seasons(state)
    assert seasons, f"{tool}: no tool call recorded a season"
    for name, season in seasons:
        assert season == "2024-25", f"{tool}: {name} sent {season}"
    dumped = json.dumps(state["calls_made"], sort_keys=True)
    assert "2025-26" not in dumped, f"{tool}: stale default leaked"


def _call_names(state):
    return [entry.partition(":")[0] for entry in state["calls_made"]]


def _assert_ratings_answers(state, tool):
    assert "get_ratings" in _call_names(state), f"{tool}: no get_ratings call"
    answers = [
        str((result.get("meta") or {}).get("deterministic_answer"))
        for result in state["tool_results"]
    ]
    assert any("2024-25" in text for text in answers), (
        f"{tool}: no ratings answer for 2024-25")
    dumped = json.dumps(state["calls_made"], sort_keys=True)
    assert "2025-26" not in dumped, f"{tool}: stale default leaked"


def test_leaders_send_derived_season(warehouse):
    state = _drive("Which player leads the league in assists last season?")
    names = [name for name, _ in _tool_seasons(state)]
    assert "get_leaders" in names
    _assert_derived_season(state, "get_leaders")


def test_single_team_ratings_send_derived_season(warehouse):
    state = _drive("What is the Lakers net rating last season?")
    _assert_ratings_answers(state, "get_ratings")


def test_two_team_compare_returns_warehouse_rows(warehouse):
    state = _drive("Compare the Lakers and Celtics net ratings last season")
    _assert_ratings_answers(state, "two-team get_ratings")
    names = set()
    for result in state["tool_results"]:
        for row in result.get("rows") or []:
            if isinstance(row, dict):
                for key in ("TEAM_NAME", "team"):
                    if row.get(key):
                        names.add(row[key])
    assert "Los Angeles Lakers" in names
    assert "Boston Celtics" in names


def test_clutch_sends_derived_season(warehouse):
    state = _drive("Who are the top clutch scorers last season?")
    names = [name for name, _ in _tool_seasons(state)]
    assert "get_clutch" in names
    _assert_derived_season(state, "get_clutch")


def test_team_compare_sends_derived_season(warehouse):
    state = _drive(
        "Top 5 teams in scoring totals with per game averages and wins?")
    names = [name for name, _ in _tool_seasons(state)]
    assert "get_team_compare" in names
    _assert_derived_season(state, "get_team_compare")


def test_rest_sends_derived_season(warehouse):
    state = _drive("Which team has the biggest rest advantage last season?")
    names = [name for name, _ in _tool_seasons(state)]
    assert "get_rest" in names
    _assert_derived_season(state, "get_rest")


def test_playoff_sim_sends_derived_season(warehouse):
    state = _drive("What are the championship odds last season?")
    names = [name for name, _ in _tool_seasons(state)]
    assert "get_playoff_sim" in names
    _assert_derived_season(state, "get_playoff_sim")


def test_trade_check_sends_derived_season(warehouse):
    state = _drive(
        "Grade the trade: Anthony Davis for Jayson Tatum, "
        "Lakers and Celtics?")
    seasons = _tool_seasons(state)
    assert ("get_trade_check", "2024-25") in seasons
    dumped = json.dumps(state["calls_made"], sort_keys=True)
    assert "2025-26" not in dumped


def test_contract_value_sends_derived_season(warehouse):
    state = _drive("Who is the most overpaid player last season?")
    names = [name for name, _ in _tool_seasons(state)]
    assert "get_contract_value" in names
    _assert_derived_season(state, "get_contract_value")


def test_explicit_season_slug_still_wins(warehouse):
    state = _drive("Compare the Lakers and Celtics net ratings in 2023-24")
    seasons = _tool_seasons(state)
    assert seasons
    for _name, season in seasons:
        assert season == "2023-24"
