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
from shared.tools._core import _warehouse_or_live


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


@pytest.fixture
def anyio_backend():
    return "asyncio"
