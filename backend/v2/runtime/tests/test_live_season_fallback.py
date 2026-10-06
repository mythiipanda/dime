from __future__ import annotations

import json

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
from v2.runtime import LedgerKind, RunLedger
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

WAREHOUSE_ROW = {
    "TEAM_ID": 97001,
    "TEAM_NAME": "Warehouse Test Franchise",
    "GP": 82,
    "W": 52,
    "L": 30,
    "OFF_RATING": 114.2,
    "DEF_RATING": 111.9,
    "NET_RATING": 2.3,
    "PACE": 98.6,
    "TS_PCT": 0.573,
    "TM_TOV_PCT": 13.2,
}

def _unfiltered_ratings_task() -> TaskSpec:
    return TaskSpec(
        goal=f"team ratings for the {REQUESTED_SEASON} season",
        mode=RunMode.QUICK,
        deliverable="team rating table",
        season=SeasonRef(value=REQUESTED_SEASON, source="user", confidence=1.0),
        requirements=[
            EvidenceRequirement(
                id="team_ratings_table",
                description=f"team ratings for {REQUESTED_SEASON}",
                capability_options=["team_ratings"],
            )
        ],
    )

def _unfiltered_ratings_plan() -> Plan:
    return Plan(nodes=[PlanNode(
        id="ratings",
        description=f"Fetch {REQUESTED_SEASON} team ratings",
        capability_hints=["team_ratings"],
        covers_requirement_ids=["team_ratings_table"],
    )])

def _recorded_ratings_executor(run_id: str):
    from v2.adapters.core import ToolCapability
    from v2.runtime import PlanExecutor, RecordedCapability

    ledger = RunLedger(run_id)
    capability = RecordedCapability(
        ToolCapability("team_ratings"), ledger, turn_id=run_id)
    return PlanExecutor({"team_ratings": capability}), ledger

def _fallback_entries(ledger) -> list:
    return [entry for entry in ledger.entries
            if entry.kind == LedgerKind.LIVE_FALLBACK]

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

@pytest.mark.anyio
async def test_warehouse_hit_consults_no_live_source_and_logs_no_fallback(
    monkeypatch, tmp_path,
) -> None:
    from shared.sources import nba_stats

    _seed_single_season_warehouse(
        monkeypatch, tmp_path, season=REQUESTED_SEASON, rows=[WAREHOUSE_ROW])

    def forbidden_live_fetch(season):
        raise AssertionError(
            f"live source consulted for a warehouse hit on {season}")

    monkeypatch.setattr(nba_stats, "team_ratings", forbidden_live_fetch)
    executor, ledger = _recorded_ratings_executor("run-live-fallback-hit")

    result = await executor.execute(_unfiltered_ratings_task(),
                                    _unfiltered_ratings_plan())

    assert result.plan.nodes[0].status == PlanStatus.COMPLETE
    assert result.errors == {}
    assert _fallback_entries(ledger) == []

@pytest.mark.anyio
async def test_warehouse_miss_with_live_success_logs_one_fallback_event_naming_both_seasons(
    monkeypatch, tmp_path,
) -> None:
    _seed_single_season_warehouse(
        monkeypatch, tmp_path, season=SEEDED_SEASON, rows=[WAREHOUSE_ROW])
    calls = _stub_live_ratings(monkeypatch, rows=[WAREHOUSE_ROW])
    executor, ledger = _recorded_ratings_executor("run-live-fallback-served")

    result = await executor.execute(_unfiltered_ratings_task(),
                                    _unfiltered_ratings_plan())

    assert calls == [REQUESTED_SEASON]
    assert result.plan.nodes[0].status == PlanStatus.COMPLETE
    entries = _fallback_entries(ledger)
    assert len(entries) == 1
    data = entries[0].data
    assert data["capability"] == "team_ratings"
    assert data["requested_season"] == REQUESTED_SEASON
    assert data["warehouse_seasons"] == [SEEDED_SEASON]
    assert data["live_source"] == "nba_api"
    assert data["outcome"] == "served"
    assert entries[0].step_id == "ratings"
    assert entries[0].call_id is not None
    assert REQUESTED_SEASON in json.dumps(data)
    assert SEEDED_SEASON in json.dumps(data)

@pytest.mark.anyio
async def test_warehouse_miss_with_live_failure_fails_loudly_naming_the_warehouse_season(
    monkeypatch, tmp_path,
) -> None:
    _seed_single_season_warehouse(
        monkeypatch, tmp_path, season=SEEDED_SEASON, rows=[WAREHOUSE_ROW])
    calls = _stub_live_ratings(
        monkeypatch, rows=[], ok=False, error="upstream returned nothing")
    executor, ledger = _recorded_ratings_executor("run-live-fallback-empty")

    result = await executor.execute(_unfiltered_ratings_task(),
                                    _unfiltered_ratings_plan())

    assert calls == [REQUESTED_SEASON]
    assert result.plan.nodes[0].status == PlanStatus.FAILED
    assert result.evidence == []
    message = result.errors["ratings"][0]
    assert REQUESTED_SEASON in message
    assert SEEDED_SEASON in message
    entries = _fallback_entries(ledger)
    assert len(entries) == 1
    assert entries[0].data["outcome"] == "empty"
    assert entries[0].data["requested_season"] == REQUESTED_SEASON
    assert entries[0].data["warehouse_seasons"] == [SEEDED_SEASON]
    assert entries[0].data["live_source"] == "nba_api"
    tool_results = [entry for entry in ledger.entries
                    if entry.kind == LedgerKind.TOOL_RESULT]
    assert tool_results[-1].data["status"] == "failed"
    assert REQUESTED_SEASON in tool_results[-1].data["error"]

@pytest.mark.anyio
async def test_fallback_event_carries_no_free_text_from_the_live_source(
    monkeypatch, tmp_path,
) -> None:
    canary = "CANARY_API_KEY_a1b2c3d4"
    _seed_single_season_warehouse(
        monkeypatch, tmp_path, season=SEEDED_SEASON, rows=[WAREHOUSE_ROW])
    _stub_live_ratings(
        monkeypatch, rows=[], ok=False,
        error=f"upstream rejected {canary} for the live request")
    executor, ledger = _recorded_ratings_executor("run-live-fallback-canary")

    await executor.execute(_unfiltered_ratings_task(),
                           _unfiltered_ratings_plan())

    entries = _fallback_entries(ledger)
    assert len(entries) == 1
    assert canary not in json.dumps(entries[0].data)
    assert set(entries[0].data) == {
        "capability", "requested_season", "warehouse_table",
        "warehouse_seasons", "live_source", "outcome"}

def _open_season() -> str:
    from shared.tools._core import (
        calendar_last_completed_season, season_static)

    start = int(calendar_last_completed_season().split("-")[0])
    for offset in range(0, 4):
        year = start + offset
        candidate = f"{year}-{(year + 1) % 100:02d}"
        if not season_static(candidate):
            return candidate
    raise AssertionError("no season is still open to a live refetch")

@pytest.mark.anyio
async def test_stale_warehouse_rows_after_a_failed_live_fetch_keep_the_fallback_record(
    monkeypatch, tmp_path,
) -> None:
    import polars as pl

    from shared.sources import nba_stats
    from shared.sources.base import FetchMeta, FetchResult
    from v2.adapters.capabilities import CAPABILITIES
    from v2.adapters.core import build_envelope

    open_season = _open_season()
    _seed_single_season_warehouse(
        monkeypatch, tmp_path, season=open_season, rows=[WAREHOUSE_ROW])
    calls: list[str] = []

    def failing_live_fetch(season):
        calls.append(season)
        return FetchResult(
            frame=pl.DataFrame(), meta=FetchMeta(source=nba_stats.SOURCE, season=season),
            ok=False, error="upstream returned nothing")

    rows, meta = _warehouse_or_live(
        "silver_team_ratings", "_season = ?", [open_season],
        lambda: failing_live_fetch(open_season), open_season,
        live_first=True)

    assert calls == [open_season]
    assert len(rows) == 1
    envelope = build_envelope(
        CAPABILITIES["team_ratings"], {"season": open_season},
        {"ok": True, "rows": rows, "meta": meta})

    assert envelope.live_fallback is not None
    assert envelope.live_fallback.outcome == "stale"
    assert envelope.live_fallback.requested_season == open_season
    assert envelope.live_fallback.warehouse_seasons == [open_season]
    assert envelope.live_fallback.live_source == "nba_api"