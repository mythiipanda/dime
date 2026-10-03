from __future__ import annotations

import pytest
from v2.contracts import (
    EvidenceRequirement,
    Plan,
    PlanNode,
    PlanStatus,
    RunMode,
    SeasonRef,
    TaskSpec,
)
from shared.tools._core import _warehouse_or_live

@pytest.fixture
def anyio_backend():
    return "asyncio"


CELTICS = {
    "TEAM_ID": 1610612738,
    "TEAM_NAME": "Boston Celtics",
    "GP": 82,
    "W": 61,
    "L": 21,
    "OFF_RATING": 120.4,
    "DEF_RATING": 111.7,
    "NET_RATING": 8.7,
    "PACE": 99.4,
    "TS_PCT": 0.604,
    "TM_TOV_PCT": 12.1,
}

SEEDED_SEASON = "2025-26"
REQUESTED_SEASON = "2024-25"


def _seed_single_season_warehouse(monkeypatch, tmp_path, *, season, rows):
    import duckdb

    from shared import store

    warehouse = tmp_path / "warehouse.duckdb"
    connection = duckdb.connect(str(warehouse))
    try:
        connection.execute(
            "CREATE TABLE silver_team_ratings (TEAM_ID INTEGER, TEAM_NAME VARCHAR, "
            "GP INTEGER, W INTEGER, L INTEGER, OFF_RATING DOUBLE, "
            "DEF_RATING DOUBLE, NET_RATING DOUBLE, PACE DOUBLE, TS_PCT DOUBLE, "
            "TM_TOV_PCT DOUBLE, _season VARCHAR, _source VARCHAR, "
            "_fetched_at VARCHAR)"
        )
        for row in rows:
            values = [row.get(key) for key in (
                "TEAM_ID", "TEAM_NAME", "GP", "W", "L", "OFF_RATING",
                "DEF_RATING", "NET_RATING", "PACE", "TS_PCT", "TM_TOV_PCT")]
            connection.execute(
                "INSERT INTO silver_team_ratings VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'fixture', "
                "'2026-04-14T00:00:00Z')",
                [*values, season],
            )
    finally:
        connection.close()
    monkeypatch.setattr(store, "DB_PATH", warehouse)
    store.warehouse_identity_cache_clear()
    from v2.adapters import coverage

    coverage.coverage_cache_clear()
    return warehouse


def _ratings_task() -> TaskSpec:
    return TaskSpec(
        goal=f"Boston Celtics {REQUESTED_SEASON} offensive and defensive rating",
        mode=RunMode.QUICK,
        deliverable="offensive and defensive team rating",
        season=SeasonRef(value=REQUESTED_SEASON, source="user", confidence=1.0),
        requirements=[
            EvidenceRequirement(
                id="celtics_team_ratings",
                description=f"Boston Celtics {REQUESTED_SEASON} team ratings",
                capability_options=["team_ratings"],
                capability_arguments={"team": "Boston Celtics"},
            )
        ],
    )


def _ratings_plan() -> Plan:
    return Plan(nodes=[PlanNode(
        id="ratings",
        description=f"Fetch Celtics {REQUESTED_SEASON} team ratings",
        capability_hints=["team_ratings"],
        covers_requirement_ids=["celtics_team_ratings"],
        arguments={"team": "Boston Celtics"},
    )])


def _stub_live_ratings(monkeypatch, *, rows, ok=True, error=""):
    import polars as pl

    from shared.sources import nba_stats
    from shared.sources.base import FetchMeta, FetchResult

    calls: list[str] = []

    def fake_team_ratings(season):
        calls.append(season)
        return FetchResult(
            frame=pl.DataFrame(rows) if rows else pl.DataFrame(),
            meta=FetchMeta(source=nba_stats.SOURCE, season=season),
            ok=ok,
            error=error,
        )

    monkeypatch.setattr(nba_stats, "team_ratings", fake_team_ratings)
    return calls


@pytest.mark.anyio
async def test_warehouse_season_miss_falls_back_to_live_source(
    monkeypatch, tmp_path,
) -> None:
    from v2.adapters.core import ToolCapability
    from v2.runtime import PlanExecutor

    _seed_single_season_warehouse(
        monkeypatch, tmp_path, season=SEEDED_SEASON, rows=[CELTICS])
    calls = _stub_live_ratings(monkeypatch, rows=[CELTICS])

    result = await PlanExecutor(
        {"team_ratings": ToolCapability("team_ratings")}
    ).execute(_ratings_task(), _ratings_plan())

    assert result.plan.nodes[0].status == PlanStatus.COMPLETE
    assert calls == [REQUESTED_SEASON]
    assert result.errors == {}
    envelope = result.evidence[0]
    assert envelope.season == REQUESTED_SEASON
    assert "nba_api" in envelope.source
    assert envelope.source_identity is not None
    assert envelope.source_identity.kind == "live"
    assert envelope.source_identity.source == "nba_api"
    assert [row["TEAM_NAME"] for row in envelope.rows] == [
        "Boston Celtics"]
    assert envelope.rows[0]["NET_RATING"] == 8.7


@pytest.mark.anyio
async def test_live_miss_on_uncovered_season_fails_with_season_availability_message(
    monkeypatch, tmp_path,
) -> None:
    from v2.adapters.core import ToolCapability
    from v2.runtime import PlanExecutor

    _seed_single_season_warehouse(
        monkeypatch, tmp_path, season=SEEDED_SEASON, rows=[CELTICS])
    calls = _stub_live_ratings(
        monkeypatch, rows=[], ok=False, error="upstream returned nothing")

    result = await PlanExecutor(
        {"team_ratings": ToolCapability("team_ratings")}
    ).execute(_ratings_task(), _ratings_plan())

    assert calls == [REQUESTED_SEASON]
    assert result.plan.nodes[0].status == PlanStatus.FAILED
    assert result.evidence == []
    assert len(result.errors["ratings"]) == 1
    message = result.errors["ratings"][0]
    assert f"Team ratings for the {REQUESTED_SEASON} season are not available" in message
    assert f"Available seasons: {SEEDED_SEASON}" in message


@pytest.mark.anyio
async def test_completed_season_warehouse_miss_stays_off_the_live_path_by_default(
    monkeypatch, tmp_path,
) -> None:
    from shared.sources import nba_stats

    _seed_single_season_warehouse(
        monkeypatch, tmp_path, season=SEEDED_SEASON, rows=[CELTICS])

    def forbidden_live_fetch(season):
        raise AssertionError("live source must not be consulted by default")

    monkeypatch.setattr(nba_stats, "team_ratings", forbidden_live_fetch)
    rows, meta = _warehouse_or_live(
        "silver_team_ratings", "_season = ?", [REQUESTED_SEASON],
        lambda: forbidden_live_fetch(REQUESTED_SEASON), REQUESTED_SEASON)

    assert rows == []
    assert meta["static_season"] is True
    assert meta["error"].startswith(
        f"no seeded rows for silver_team_ratings ({REQUESTED_SEASON})")


@pytest.mark.anyio
async def test_seeded_season_is_answered_from_the_warehouse_without_live_fetch(
    monkeypatch, tmp_path,
) -> None:
    from v2.adapters.core import ToolCapability
    from v2.runtime import PlanExecutor

    _seed_single_season_warehouse(
        monkeypatch, tmp_path, season=REQUESTED_SEASON, rows=[CELTICS])
    calls = _stub_live_ratings(monkeypatch, rows=[CELTICS])

    task = _ratings_task()
    plan = _ratings_plan()
    result = await PlanExecutor(
        {"team_ratings": ToolCapability("team_ratings")}
    ).execute(task, plan)

    assert result.plan.nodes[0].status == PlanStatus.COMPLETE
    assert calls == []
    assert result.errors == {}
    assert "fixture" in result.evidence[0].source