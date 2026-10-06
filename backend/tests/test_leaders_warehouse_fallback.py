import sys
from pathlib import Path

import duckdb
import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources import nba_stats
from shared.sources.base import FetchMeta, FetchResult
from v2.adapters.core import call_capability
from v2.domain.evidence import admit_evidence

SEASON = "2024-25"
ABSENT_STATIC_SEASON = "2023-24"

def _seed_leaders(path, seasons):
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE silver_leaders_ast (RANK BIGINT, PLAYER VARCHAR, "
            "TEAM VARCHAR, GP BIGINT, AST BIGINT, MIN BIGINT, "
            "PLAYER_ID BIGINT, TEAM_ID BIGINT, "
            "_source VARCHAR, _season VARCHAR, _fetched_at VARCHAR)"
        )
        for season in seasons:
            if season == SEASON:
                connection.execute(
                    "INSERT INTO silver_leaders_ast VALUES "
                    "(1, 'Trae Young', 'ATL', 76, 880, 2739, 1629027, "
                    "1610612737, 'nba_stats', '2024-25', "
                    "'2026-09-08T00:00:00+00:00'), "
                    "(2, 'Nikola Jokic', 'DEN', 70, 716, 2500, 203999, "
                    "1610612743, 'nba_stats', '2024-25', "
                    "'2026-09-08T00:00:00+00:00')"
                )
            else:
                connection.execute(
                    "INSERT INTO silver_leaders_ast VALUES "
                    "(1, 'Open Star', 'BOS', 70, 700, 2400, 1628369, "
                    "1610612738, 'nba_stats', ?, "
                    "'2026-09-08T00:00:00+00:00')",
                    [season],
                )
    finally:
        connection.close()

@pytest.fixture()
def warehouse(monkeypatch, tmp_path):
    path = tmp_path / "leaders_fallback.duckdb"
    _seed_leaders(path, [SEASON])
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store._tables_cache.clear()
    store._pool_evict_all()
    store.warehouse_identity_cache_clear()
    from v2.adapters import coverage

    coverage.coverage_cache_clear()
    yield path
    coverage.coverage_cache_clear()

def _open_season():
    from shared.tools._core import calendar_last_completed_season, season_static

    start = int(calendar_last_completed_season().split("-")[0])
    for offset in range(0, 4):
        year = start + offset
        candidate = f"{year}-{(year + 1) % 100:02d}"
        if not season_static(candidate):
            return candidate
    raise AssertionError("no open season available")

def test_assists_answered_from_warehouse_with_zero_live_calls(
    warehouse, monkeypatch
):
    calls = []

    def forbidden(season):
        calls.append(season)
        raise AssertionError("live consulted on a warehouse hit")

    monkeypatch.setattr(nba_stats, "leaders", forbidden)
    envelope = call_capability(
        "qualified_leaders", {"stat_category": "AST", "season": SEASON}
    )
    assert calls == []
    assert envelope.live_fallback is None
    assert envelope.season == SEASON
    assert envelope.rows[0]["PLAYER"] == "Trae Young"
    assert envelope.rows[0]["AST"] == 880
    assert envelope.rows[0]["GP"] == 76
    assert envelope.rows[0]["PLAYER_NAME"] == "Trae Young"
    assert envelope.rows[0]["AST_PER_GAME"] == 11.6
    admit_evidence(envelope, required_season=SEASON)

def test_absent_open_season_takes_live_path_with_one_fallback_event(
    warehouse, monkeypatch, tmp_path
):
    from v2.adapters.core import ToolCapability
    from v2.runtime import LedgerKind, PlanExecutor, RunLedger
    from v2.runtime.recording import RecordedCapability
    from v2.contracts import (
        EvidenceRequirement,
        Plan,
        PlanNode,
        PlanStatus,
        SeasonRef,
        TaskSpec,
    )

    requested = _open_season()
    assert requested != SEASON
    calls = []

    def fake_leaders(stat_category, season):
        calls.append((stat_category, season))
        return FetchResult(
            frame=pl.DataFrame(
                {
                    "PLAYER_ID": [1629027, 203999],
                    "RANK": [1, 2],
                    "PLAYER": ["Trae Young", "Nikola Jokic"],
                    "TEAM_ID": [1610612737, 1610612743],
                    "TEAM": ["ATL", "DEN"],
                    "GP": [76, 70],
                    "MIN": [2739, 2500],
                    "AST": [880, 716],
                }
            ),
            meta=FetchMeta(source=nba_stats.SOURCE, season=season),
        )

    monkeypatch.setattr(nba_stats, "leaders", fake_leaders)
    run_id = "run-leaders-fallback-served"
    ledger = RunLedger(run_id)
    capability = RecordedCapability(
        ToolCapability("qualified_leaders"), ledger, turn_id=run_id
    )
    executor = PlanExecutor({"qualified_leaders": capability})
    task = TaskSpec(
        goal="assists leader",
        mode="quick",
        deliverable="assists leader",
        season=SeasonRef(value=requested, source="user", confidence=1.0),
        requirements=[
            EvidenceRequirement(
                id="assist_leader",
                description="assists leader",
                capability_options=["qualified_leaders"],
                capability_arguments={
                    "stat_category": "AST",
                    "season": requested,
                },
            )
        ],
    )
    plan = Plan(
        nodes=[
            PlanNode(
                id="leader",
                description="assists board",
                capability_hints=["qualified_leaders"],
                covers_requirement_ids=["assist_leader"],
                arguments={"stat_category": "AST", "season": requested},
                status=PlanStatus.PENDING,
            )
        ]
    )
    import anyio

    result = anyio.run(executor.execute, task, plan)
    assert calls == [("AST", requested)]
    assert result.plan.nodes[0].status == PlanStatus.COMPLETE
    assert result.errors == {}
    fallbacks = [
        entry for entry in ledger.entries if entry.kind == LedgerKind.LIVE_FALLBACK
    ]
    assert len(fallbacks) == 1
    data = fallbacks[0].data
    assert data["capability"] == "qualified_leaders"
    assert data["requested_season"] == requested
    assert data["warehouse_seasons"] == sorted([SEASON, requested])
    assert data["live_source"] == "nba_api"
    assert data["outcome"] == "served"
    envelope = result.evidence[0]
    assert envelope.rows[0]["AST"] == 880
    assert envelope.rows[0]["PLAYER_NAME"] == "Trae Young"
    admit_evidence(envelope, required_season=requested)

def test_live_shaped_rows_bind_same_as_warehouse_shaped_rows(
    warehouse, monkeypatch
):
    from v2.contracts import (
        Claim,
        ClaimKind,
        DraftReport,
        EvidenceRequirement,
        SeasonRef,
        TaskSpec,
    )
    from v2.runtime.verifier import verify_mechanical

    warehouse_envelope = call_capability(
        "qualified_leaders", {"stat_category": "AST", "season": SEASON}
    )

    requested = _open_season()

    def fake_leaders(stat_category, season):
        return FetchResult(
            frame=pl.DataFrame(
                {
                    "PLAYER_ID": [1629027],
                    "RANK": [1],
                    "PLAYER": ["Trae Young"],
                    "TEAM_ID": [1610612737],
                    "TEAM": ["ATL"],
                    "GP": [76],
                    "MIN": [2739],
                    "AST": [880],
                }
            ),
            meta=FetchMeta(source=nba_stats.SOURCE, season=season),
        )

    monkeypatch.setattr(nba_stats, "leaders", fake_leaders)
    live_envelope = call_capability(
        "qualified_leaders", {"stat_category": "AST", "season": requested}
    )
    for envelope, season in (
        (warehouse_envelope, SEASON),
        (live_envelope, requested),
    ):
        row = envelope.rows[0]
        assert row["PLAYER_NAME"] == "Trae Young"
        assert row["AST"] == 880
        assert row["GP"] == 76
        task = TaskSpec(
            goal="assists leader",
            mode="quick",
            deliverable="assists leader",
            requested_outputs=["PLAYER_NAME", "AST"],
            season=SeasonRef(value=season, source="user", confidence=1.0),
            requirements=[
                EvidenceRequirement(
                    id="assist_leader",
                    description="assists leader",
                    capability_options=["qualified_leaders"],
                    capability_arguments={
                        "stat_category": "AST",
                        "season": season,
                    },
                    requested_outputs=["PLAYER_NAME", "AST"],
                )
            ],
        )
        claim = Claim(
            text="Trae Young led with 880 assists.",
            kind=ClaimKind.OBSERVED,
            evidence_ids=[envelope.evidence_id],
            output_bindings=[],
        )
        draft = DraftReport(sections=["leader"], claims=[claim], gaps=[])
        report = verify_mechanical(task, draft, [envelope])
        assert report.claim_results[0].supported is True

def test_static_miss_without_warehouse_rows_fails_loudly(
    warehouse, monkeypatch
):
    from shared.tools.league import get_leaders

    calls = []

    def forbidden(stat_category, season):
        calls.append((stat_category, season))
        raise AssertionError("live consulted for a static miss")

    monkeypatch.setattr(nba_stats, "leaders", forbidden)
    result = get_leaders.invoke(
        {"stat_category": "AST", "season": ABSENT_STATIC_SEASON}
    )
    assert calls == []
    assert result["ok"] is False
    assert result["rows"] == []
    assert ABSENT_STATIC_SEASON in result["error"]
