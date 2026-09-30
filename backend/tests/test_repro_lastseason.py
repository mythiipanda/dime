import asyncio
import json
import re
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _detect_entities, _triage_seed
from shared import store
from shared.tools import league as league_tools
from shared.tools._core import last_completed_season

QUESTION = "Compare the Lakers and Celtics net ratings last season"

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
    {
        "TEAM_ID": 14,
        "TEAM_NAME": "Los Angeles Lakers",
        "GP": 82,
        "W": 47,
        "L": 35,
        "OFF_RATING": 115.2,
        "DEF_RATING": 113.1,
        "NET_RATING": 2.1,
        "PACE": 99.5,
        "TS_PCT": 0.585,
        "TM_TOV_PCT": 12.1,
    },
    {
        "TEAM_ID": 2,
        "TEAM_NAME": "Boston Celtics",
        "GP": 82,
        "W": 59,
        "L": 23,
        "OFF_RATING": 120.1,
        "DEF_RATING": 110.3,
        "NET_RATING": 9.8,
        "PACE": 98.7,
        "TS_PCT": 0.605,
        "TM_TOV_PCT": 11.4,
    },
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
        for row in RATINGS_ROWS:
            connection.execute(
                "INSERT INTO silver_team_ratings VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    row["TEAM_ID"],
                    row["TEAM_NAME"],
                    row["GP"],
                    row["W"],
                    row["L"],
                    row["OFF_RATING"],
                    row["DEF_RATING"],
                    row["NET_RATING"],
                    row["PACE"],
                    row["TS_PCT"],
                    row["TM_TOV_PCT"],
                    "2024-25",
                    "seed",
                    "2024-01-01",
                ],
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
    path = tmp_path / "repro.duckdb"
    _seed(path)
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store._tables_cache.clear()
    store._pool_evict_all()
    store.warehouse_identity_cache_clear()
    return path


def _drive_fast_path(question):
    state = {
        "question": question,
        "history": [],
        "tool_results": [],
        "calls_made": [],
    }

    async def _collect():
        seen = []
        async for event in _triage_seed(question, "primary", "model", state):
            seen.append(event)
        return seen

    events = asyncio.run(_collect())
    return state, events


def _seasons_from_calls(calls):
    found = []
    for entry in calls:
        name, _, blob = entry.partition(":")
        try:
            args = json.loads(blob)
        except Exception:
            continue
        if isinstance(args, dict) and args.get("season"):
            found.append((name, args["season"]))
    return found


def _resolved_season(state):
    sent = _seasons_from_calls(state["calls_made"])
    if sent:
        return sent[0][1]
    return last_completed_season()


def test_warehouse_most_recent_season_is_2024_25(warehouse):
    assert store.latest_data_season() == "2024-25"


def test_fast_path_entities_cover_both_teams(warehouse):
    _players, teams = _detect_entities(QUESTION)
    assert len(teams) == 2


def test_fast_path_sends_most_recent_warehouse_season(warehouse):
    state, _events = _drive_fast_path(QUESTION)
    assert _resolved_season(state) == "2024-25"


def test_resolved_season_returns_lakers_celtics_ratings(warehouse):
    state, _events = _drive_fast_path(QUESTION)
    out = league_tools.get_ratings.invoke(
        {"season": _resolved_season(state)})
    rows = out.get("rows") or []
    names = {row.get("TEAM_NAME") for row in rows}
    assert {"Los Angeles Lakers", "Boston Celtics"} <= names
