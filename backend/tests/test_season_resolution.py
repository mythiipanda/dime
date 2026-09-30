import asyncio
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _triage_seed
from shared import store
from shared.tools import _core as core_mod
from shared.tools.league import get_ratings
from v2.adapters import coverage as coverage_mod

QUESTION = "Compare the Lakers and Celtics net ratings last season"

BOXSCORE_SEASONS = [
    "2015-16",
    "2016-17",
    "2017-18",
    "2018-19",
    "2019-20",
    "2020-21",
    "2021-22",
    "2022-23",
    "2023-24",
]

WAREHOUSE_MAX = "2024-25"

RATINGS_ROWS = [
    (14, "Los Angeles Lakers", 82, 47, 35, 115.2, 113.1, 2.1),
    (2, "Boston Celtics", 82, 59, 23, 120.1, 110.3, 9.8),
]


def _seed(path):
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE silver_boxscores (_season VARCHAR, GAME_ID VARCHAR)"
        )
        for season in BOXSCORE_SEASONS:
            connection.execute(
                "INSERT INTO silver_boxscores VALUES (?, ?)",
                [season, "002" + season[:4] + "00001"],
            )
        connection.execute(
            "CREATE TABLE silver_hist_standings "
            "(_season VARCHAR, TEAM_NAME VARCHAR)"
        )
        for season in BOXSCORE_SEASONS + [WAREHOUSE_MAX]:
            connection.execute(
                "INSERT INTO silver_hist_standings VALUES (?, ?)",
                [season, "Los Angeles Lakers"],
            )
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
    finally:
        connection.close()


@pytest.fixture()
def warehouse(monkeypatch, tmp_path):
    path = tmp_path / "seasonres.duckdb"
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


def _result_names(state):
    names = set()
    for result in state["tool_results"]:
        for row in result.get("rows") or []:
            if isinstance(row, dict):
                for key in ("TEAM_NAME", "TEAM"):
                    if row.get(key):
                        names.add(row[key])
    return names


def _answers(state):
    texts = []
    for result in state["tool_results"]:
        meta = result.get("meta") or {}
        if isinstance(meta, dict) and meta.get("deterministic_answer"):
            texts.append(str(meta["deterministic_answer"]))
    return texts


def test_compare_returns_warehouse_max_season_rows(warehouse):
    state = _drive(QUESTION)
    assert {"Los Angeles Lakers", "Boston Celtics"} <= _result_names(state)
    assert any(WAREHOUSE_MAX in text for text in _answers(state))


def test_ratings_gap_asks_instead_of_empty_answer(warehouse):
    out = get_ratings.invoke({"season": "2023-24"})
    assert out.get("ok") is False
    assert WAREHOUSE_MAX in str(out.get("error") or "")
    assert WAREHOUSE_MAX in str(
        (out.get("meta") or {}).get("deterministic_answer") or "")
