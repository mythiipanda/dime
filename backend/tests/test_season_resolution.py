import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph as graph_mod
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


def test_compare_sends_calendar_season_with_coverage_refusal(warehouse):
    expected = _calendar_season()
    state = _drive(QUESTION)
    sent = []
    for entry in state["calls_made"]:
        _name, _, blob = entry.partition(":")
        try:
            args = json.loads(blob)
        except Exception:
            continue
        if isinstance(args, dict) and args.get("season"):
            sent.append(args["season"])
    assert sent
    assert all(season == expected for season in sent)
    assert all(season != WAREHOUSE_MAX for season in sent)
    refusals = [result for result in state["tool_results"]
                if result.get("season_error") is True]
    assert refusals
    assert all(expected in str(result.get("error") or "")
                for result in refusals)


def test_compare_refusal_reaches_final_answer(warehouse):
    expected = _calendar_season()
    state = _drive(QUESTION)
    asked = dict(state)
    asked["primary"] = "p"
    asked["model"] = "m"

    async def _collect():
        texts = []
        async for event in graph_mod.presentation_agent(asked):
            if event.get("type") == "final_answer":
                texts.append(str((event.get("data") or {}).get("text", "")))
        return texts

    texts = asyncio.run(_collect())
    assert texts
    assert expected in texts[-1]
    assert "could not find that in the dataset" not in texts[-1]


def test_ratings_gap_asks_instead_of_empty_answer(warehouse, monkeypatch):
    from shared.sources import nba_stats
    from shared.sources.base import FetchMeta, FetchResult
    import polars as pl

    def unavailable(season):
        return FetchResult(
            frame=pl.DataFrame(),
            meta=FetchMeta(source=nba_stats.SOURCE, season=season),
            ok=False, error="upstream returned nothing")

    monkeypatch.setattr(nba_stats, "team_ratings", unavailable)
    out = get_ratings.invoke({"season": "2023-24"})
    assert out.get("ok") is False
    assert WAREHOUSE_MAX in str(out.get("error") or "")
    assert WAREHOUSE_MAX in str(
        (out.get("meta") or {}).get("deterministic_answer") or "")
