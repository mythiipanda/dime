import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph as graph_mod
from app.graph import _detect_entities, _triage_seed
from shared import store
from shared.tools import _core as core_mod
from v2.adapters import coverage as coverage_mod

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

WAREHOUSE_MAX = "2024-25"

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
                    WAREHOUSE_MAX,
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


def _final_answer_text(question, state):
    asked = dict(state)
    asked["primary"] = "p"
    asked["model"] = "m"

    async def _collect():
        texts = []
        async for event in graph_mod.presentation_agent(asked):
            if event.get("type") == "final_answer":
                data = event.get("data") or {}
                texts.append(str(data.get("text", "")))
        return texts

    texts = asyncio.run(_collect())
    assert texts, "presentation produced no final answer"
    return texts[-1]


def test_completed_season_for_date_anchors_to_calendar():
    assert core_mod.completed_season_for_date(dt.date(2026, 10, 1)) == "2025-26"
    assert core_mod.completed_season_for_date(dt.date(2026, 3, 15)) == "2024-25"
    assert core_mod.completed_season_for_date(dt.date(2026, 8, 1)) == "2025-26"
    assert core_mod.completed_season_for_date(dt.date(2026, 7, 1)) == "2025-26"
    assert core_mod.completed_season_for_date(dt.date(2026, 6, 30)) == "2024-25"
    assert core_mod.completed_season_for_date(dt.date(2025, 10, 15)) == "2024-25"
    assert core_mod.completed_season_for_date(dt.date(2025, 2, 1)) == "2023-24"
    assert core_mod.completed_season_for_date(
        dt.datetime(2026, 10, 1, 12, 0)) == "2025-26"


def test_warehouse_most_recent_season_is_2024_25(warehouse):
    assert store.latest_data_season() == WAREHOUSE_MAX


def test_fast_path_entities_cover_both_teams(warehouse):
    _players, teams = _detect_entities(QUESTION)
    assert len(teams) == 2


def test_last_season_resolves_to_calendar_completed_season(warehouse):
    expected = _calendar_season()
    state, _events = _drive_fast_path(QUESTION)
    sent = _seasons_from_calls(state["calls_made"])
    assert sent, "no tool call recorded a season"
    for _name, season in sent:
        assert season == expected


def test_last_season_never_substitutes_warehouse_max(warehouse):
    expected = _calendar_season()
    state, _events = _drive_fast_path(QUESTION)
    sent = _seasons_from_calls(state["calls_made"])
    assert sent
    assert all(season != WAREHOUSE_MAX for _, season in sent)
    for result in state["tool_results"]:
        assert result.get("season_error") is True
        assert expected in str(result.get("error") or "")


@pytest.mark.parametrize("phrase", ["last season", "this season",
                                    "current season"])
def test_relative_phrases_resolve_to_calendar(warehouse, phrase):
    expected = _calendar_season()
    question = f"Compare the Lakers and Celtics net ratings {phrase}"
    state, _events = _drive_fast_path(question)
    sent = _seasons_from_calls(state["calls_made"])
    assert sent, f"{phrase}: no tool call recorded a season"
    for _name, season in sent:
        assert season == expected, f"{phrase}: sent {season}"


def test_explicit_season_passes_through_with_rows(warehouse):
    state, _events = _drive_fast_path(
        "Compare the Lakers and Celtics net ratings in 2024-25")
    sent = _seasons_from_calls(state["calls_made"])
    assert sent
    for _name, season in sent:
        assert season == "2024-25"
    names = set()
    answers = []
    for result in state["tool_results"]:
        assert result.get("season_error") is not True
        for row in result.get("rows") or []:
            if isinstance(row, dict) and row.get("TEAM_NAME"):
                names.add(row["TEAM_NAME"])
        meta = result.get("meta") or {}
        if meta.get("deterministic_answer"):
            answers.append(str(meta["deterministic_answer"]))
    assert {"Los Angeles Lakers", "Boston Celtics"} <= names
    assert any("2024-25" in text for text in answers)


def test_question_without_season_keeps_warehouse_default(warehouse):
    state, _events = _drive_fast_path(
        "Compare the Lakers and Celtics net ratings")
    names = set()
    for result in state["tool_results"]:
        for row in result.get("rows") or []:
            if isinstance(row, dict) and row.get("TEAM_NAME"):
                names.add(row["TEAM_NAME"])
    assert {"Los Angeles Lakers", "Boston Celtics"} <= names


def test_last_season_final_answer_names_uncovered_season(warehouse):
    expected = _calendar_season()
    state, _events = _drive_fast_path(QUESTION)
    text = _final_answer_text(QUESTION, state)
    assert expected in text
    assert "could not find that in the dataset" not in text
