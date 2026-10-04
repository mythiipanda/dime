import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store  # noqa: E402
from shared.tools.league import get_leaders, get_ratings  # noqa: E402
from v2.adapters import coverage as coverage_mod  # noqa: E402
from v2.adapters.core import call_capability  # noqa: E402
from v2.domain.evidence import admit_evidence  # noqa: E402

SEASON = "2024-25"


_HIST_COLUMNS = (
    "team_id BIGINT, team_abbreviation VARCHAR, game_id VARCHAR, "
    "game_date DATE, matchup VARCHAR, wl VARCHAR, min DOUBLE, "
    "fgm INTEGER, fga INTEGER, fg_pct DOUBLE, "
    "fg3m INTEGER, fg3a INTEGER, fg3_pct DOUBLE, "
    "ftm INTEGER, fta INTEGER, ft_pct DOUBLE, "
    "oreb INTEGER, dreb INTEGER, reb INTEGER, "
    "ast INTEGER, stl INTEGER, blk INTEGER, "
    "tov INTEGER, pf INTEGER, pts INTEGER, "
    "season_type VARCHAR, _season VARCHAR"
)

_HIST_ROWS = [
    (1610612738, "BOS", "0022400001", "2024-10-22", "BOS vs. NYK", "W",
     240.0, 46, 100, 0.460, 10, 32, 0.3125, 18, 20, 0.900,
     10, 30, 40, 25, 7, 4, 12, 20, 120, "regular-season", SEASON),
    (1610612752, "NYK", "0022400001", "2024-10-22", "NYK @ BOS", "L",
     240.0, 41, 94, 0.436, 9, 30, 0.300, 15, 18, 0.833,
     8, 31, 39, 22, 6, 3, 14, 22, 110, "regular-season", SEASON),
    (1610612738, "BOS", "0022400002", "2024-11-05", "BOS @ NYK", "W",
     240.0, 45, 89, 0.506, 8, 28, 0.286, 20, 22, 0.909,
     9, 33, 42, 27, 5, 6, 13, 19, 118, "regular-season", SEASON),
    (1610612752, "NYK", "0022400002", "2024-11-05", "NYK vs. BOS", "L",
     240.0, 40, 84, 0.476, 8, 26, 0.308, 17, 20, 0.850,
     11, 28, 39, 23, 8, 2, 15, 24, 105, "regular-season", SEASON),
    (1610612738, "BOS", "0042400101", "2024-04-20", "BOS vs. NYK", "W",
     240.0, 48, 100, 0.480, 14, 36, 0.389, 22, 26, 0.846,
     12, 34, 46, 28, 9, 5, 15, 22, 140, "playoffs", SEASON),
    (1610612752, "NYK", "0042400101", "2024-04-20", "NYK @ BOS", "L",
     240.0, 44, 96, 0.458, 11, 32, 0.344, 18, 20, 0.900,
     9, 30, 39, 21, 7, 4, 16, 23, 128, "playoffs", SEASON),
]


def _seed(path):
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE silver_leaders_ast (RANK BIGINT, PLAYER VARCHAR, "
            "TEAM VARCHAR, GP BIGINT, AST BIGINT, MIN BIGINT, "
            "_source VARCHAR, _season VARCHAR, _fetched_at VARCHAR)"
        )
        connection.execute(
            "INSERT INTO silver_leaders_ast VALUES "
            "(1, 'Trae Young', 'ATL', 76, 880, 2739, 'nba_stats', "
            "'2024-25', '2025-06-01T00:00:00+00:00'), "
            "(2, 'Nikola Jokic', 'DEN', 70, 716, 2500, 'nba_stats', "
            "'2024-25', '2025-06-01T00:00:00+00:00'), "
            "(1, 'Current Star', 'DEN', 65, 697, 2200, 'nba_stats', "
            "'2025-26', '2026-09-30T00:00:00+00:00')"
        )
        connection.execute(
            f"CREATE TABLE silver_hist_gamelogs ({_HIST_COLUMNS})")
        connection.executemany(
            f"INSERT INTO silver_hist_gamelogs "
            f"VALUES ({', '.join('?' * 27)})",
            [list(row) for row in _HIST_ROWS],
        )
    finally:
        connection.close()


@pytest.fixture()
def warehouse(monkeypatch, tmp_path):
    path = tmp_path / "execgap.duckdb"
    _seed(path)
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store._tables_cache.clear()
    store._pool_evict_all()
    store.warehouse_identity_cache_clear()
    coverage_mod.coverage_cache_clear()
    yield path
    coverage_mod.coverage_cache_clear()


def test_assists_full_name_selects_assists_board(warehouse):
    result = get_leaders.invoke(
        {"stat_category": "assists", "season": SEASON})
    assert result["ok"] is True
    assert result["rows"][0]["PLAYER"] == "Trae Young"
    assert result["rows"][0]["AST"] == 880
    assert result["rows"][0]["GP"] == 76


def test_descending_direction_accepted(warehouse):
    result = get_leaders.invoke(
        {"stat_category": "AST", "season": SEASON,
         "ranking_direction": "descending"})
    assert result["ok"] is True
    assert result["rows"][0]["PLAYER"] == "Trae Young"
    assert result["rows"][0]["AST"] == 880


def test_qualified_leaders_capability_binds_full_name(warehouse):
    envelope = call_capability(
        "qualified_leaders",
        {"stat_category": "assists", "season": SEASON})
    assert envelope.rows[0]["AST"] == 880
    assert envelope.units["AST"] == "count"
    admit_evidence(envelope, required_season=SEASON)


def test_missing_ratings_season_estimated_from_gamelogs(warehouse):
    result = get_ratings.invoke({"season": SEASON, "team": "BOS"})
    assert result["ok"] is True
    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["TEAM_NAME"] == "Boston Celtics"
    assert row["GP"] == 2
    assert (row["W"], row["L"]) == (2, 0)
    assert row["OFF_RATING"] == 114.7
    assert row["DEF_RATING"] == 103.6
    assert row["NET_RATING"] == 11.1
    assert row["PACE"] == 103.74
    assert result["meta"]["ratings_provenance"] == "derived"
    assert result["meta"]["ratings_source"] == "silver_hist_gamelogs"
    assert "derived" in result["meta"]["source"]


def test_team_ratings_capability_binds_gamelog_fallback(warehouse):
    envelope = call_capability(
        "team_ratings", {"season": SEASON, "team": "Celtics"})
    assert envelope.season == SEASON
    assert envelope.rows[0]["NET_RATING"] == 11.1
    assert envelope.units["NET_RATING"] == "points_per_100_possessions"
    admit_evidence(envelope, required_season=SEASON)


def test_ratings_refusal_preserved_without_gamelogs(warehouse, monkeypatch):
    from shared.sources import nba_stats
    from shared.sources.base import FetchMeta, FetchResult
    import polars as pl

    def unavailable(season):
        return FetchResult(
            frame=pl.DataFrame(),
            meta=FetchMeta(source=nba_stats.SOURCE, season=season),
            ok=False, error="upstream returned nothing")

    monkeypatch.setattr(nba_stats, "team_ratings", unavailable)
    result = get_ratings.invoke({"season": "2023-24", "team": "BOS"})
    assert result["ok"] is False
    assert result["rows"] == []
    assert "2023-24" in str(result["error"])
    assert "not available" in str(result["error"])


def test_clamp_stat_rejects_unknown_category():
    from shared.tools import clamp_stat

    with pytest.raises(ValueError):
        clamp_stat("total assists")


def test_unknown_stat_category_fails_loudly(warehouse):
    result = get_leaders.invoke(
        {"stat_category": "total assists", "season": SEASON})
    assert result["ok"] is False
    assert result["rows"] == []
    assert "total assists" in result["error"]


def test_natural_ratings_claim_passes_without_unit_phrase(warehouse):
    from v2.contracts import (
        Claim, ClaimKind, DraftReport, EvidenceRequirement,
        SeasonRef, TaskSpec,
    )
    from v2.runtime.verifier import verify_mechanical
    envelope = call_capability(
        "team_ratings", {"season": SEASON, "team": "BOS"})
    task = TaskSpec(
        goal="What were the Celtics' net rating, offensive rating, "
             "and defensive rating in the 2024-25 season?",
        mode="quick", deliverable="Celtics ratings",
        requested_outputs=["NET_RATING", "OFF_RATING", "DEF_RATING"],
        season=SeasonRef(value=SEASON, source="user", confidence=1.0),
        requirements=[EvidenceRequirement(
            id="celtics_ratings",
            description="Celtics 2024-25 ratings",
            capability_options=["team_ratings"],
            capability_arguments={"season": SEASON, "team": "BOS"},
            requested_outputs=["NET_RATING", "OFF_RATING", "DEF_RATING"])])
    claim = Claim(
        text="The Boston Celtics had a net rating of 11.1, an offensive "
             "rating of 114.7, and a defensive rating of 103.6 "
             "in the 2024-25 season.",
        kind=ClaimKind.OBSERVED, evidence_ids=[envelope.evidence_id],
        output_bindings=[])
    draft = DraftReport(
        sections=["Celtics ratings"], claims=[claim], gaps=[])
    report = verify_mechanical(task, draft, [envelope])
    assert report.status.value == "pass"
    assert report.claim_results[0].supported is True


def test_player_name_output_binds_leader_row(warehouse):
    from v2.contracts import (
        Claim, ClaimKind, DraftReport, EvidenceOutputBinding,
        EvidenceRequirement, Plan, PlanNode, PlanStatus,
        SeasonRef, TaskSpec, VerifiedClaim,
    )
    from v2.runtime.models import (
        ExecutionResult, admit_verified_claim_bindings,
    )
    envelope = call_capability(
        "qualified_leaders",
        {"stat_category": "assists", "season": SEASON})
    assert envelope.rows[0]["PLAYER"] == "Trae Young"
    task = TaskSpec(
        goal="Who led the NBA in assists in the 2024-25 season, and how many?",
        mode="quick", deliverable="Assists leader and total assists",
        requested_outputs=["AST"],
        season=SeasonRef(value=SEASON, source="user", confidence=1.0),
        requirements=[EvidenceRequirement(
            id="assist_leader_2024_25",
            description="2024-25 NBA assists leader",
            capability_options=["qualified_leaders"],
            capability_arguments={"stat_category": "AST", "season": SEASON},
            requested_outputs=["PLAYER_NAME", "AST"])])
    plan = Plan(nodes=[PlanNode(
        id="leader", description="Fetch 2024-25 assists leaderboard",
        capability_hints=["qualified_leaders"],
        covers_requirement_ids=["assist_leader_2024_25"],
        arguments={"stat_category": "AST", "season": SEASON},
        status=PlanStatus.COMPLETE)])
    execution = ExecutionResult(
        plan=plan, evidence_by_node={"leader": envelope},
        attempts={"leader": 1})
    bindings = [
        EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id="assist_leader_2024_25", output_id="AST",
            node_id="leader", evidence_id=envelope.evidence_id,
            selector="rows[0].AST",
            value={"kind": "integer", "value": 880},
            unit={"kind": "declared", "value": "count"},
            domain="qualified_leaders"),
        EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id="assist_leader_2024_25", output_id="PLAYER_NAME",
            node_id="leader", evidence_id=envelope.evidence_id,
            selector="rows[0].PLAYER_NAME",
            value={"kind": "string", "value": "Trae Young"},
            unit={"kind": "unitless"},
            domain="qualified_leaders"),
    ]
    claim = Claim(
        text="Trae Young led the NBA with 880 assists in 2024-25.",
        kind=ClaimKind.OBSERVED, evidence_ids=[envelope.evidence_id],
        output_bindings=bindings)
    draft = DraftReport(sections=["Assists leader"], claims=[claim], gaps=[])
    candidate = VerifiedClaim(
        claim_index=0, claim=claim, evidence_ids=[envelope.evidence_id],
        sources=[{"evidence_id": envelope.evidence_id,
                  "source": envelope.source,
                  "capability": envelope.capability,
                  "observed_at": envelope.observed_at,
                  "as_of": envelope.as_of,
                  "vintages": dict(envelope.vintages)}],
        output_bindings=bindings)
    assert admit_verified_claim_bindings(
        task, execution, draft, candidate) is candidate


def test_task_scoped_binding_with_requirement_id_stays_task_scoped():
    from v2.contracts import EvidenceOutputBinding
    binding = EvidenceOutputBinding.model_validate({
        "requirement_kind": "task",
        "requirement_id": "assist_leader_2024_25",
        "output_id": "AST",
        "node_id": "assist_leader_2024_25",
        "evidence_id": "qualified_leaders:0123456789abcdef",
        "selector": "rows[0].AST",
        "value": {"kind": "integer", "value": 880},
        "unit": {"kind": "declared", "value": "count"},
        "domain": "qualified_leaders",
    })
    assert binding.requirement_kind == "task"
    assert binding.requirement_id is None


def test_synthesizer_keeps_task_scoped_llm_bindings(warehouse):
    import asyncio
    import json
    from pydantic import TypeAdapter
    from v2.adapters.models import ModelSynthesizer
    from v2.contracts import (
        Claim, ClaimKind, DraftReport, EvidenceRequirement,
        SeasonRef, TaskSpec,
    )
    envelope = call_capability(
        "qualified_leaders",
        {"stat_category": "AST", "season": SEASON})
    assert envelope.rows[0]["AST"] == 880
    task = TaskSpec(
        goal="Identify the player who led the NBA in assists during "
             "the 2024-25 season and report their assist total.",
        mode="quick",
        deliverable="The name of the assist leader for the 2024-25 NBA "
                    "season and their total number of assists.",
        metric_ids=["AST"],
        requested_outputs=["PLAYER_NAME", "AST"],
        season=SeasonRef(value=SEASON, source="user", confidence=1.0),
        requirements=[EvidenceRequirement(
            id="assist_leader_2024_25",
            description="Identify the player who led the NBA in assists "
                        "during the 2024-25 season and report their total.",
            capability_options=["qualified_leaders"],
            capability_arguments={
                "stat_category": "AST", "season": SEASON,
                "min_attempts": 0, "ranking_direction": "desc"},
            metric_ids=["AST"],
            requested_outputs=["PLAYER_NAME", "AST"])])

    class StubModel:
        async def generate(self, **call):
            schema = call["schema"]
            evidence_id = call["payload"]["evidence"][0]["evidence_id"]
            draft = {
                "sections": ["Assists leader"],
                "claims": [{
                    "text": "Trae Young led the NBA with 880 assists in "
                            "76 games in 2024-25.",
                    "kind": "observed",
                    "evidence_ids": [evidence_id],
                    "output_bindings": [
                        {"requirement_kind": "task",
                         "requirement_id": "assist_leader_2024_25",
                         "output_id": "AST",
                         "node_id": "assist_leader_2024_25",
                         "evidence_id": evidence_id,
                         "selector": "rows[0].AST",
                         "value": {"kind": "integer", "value": 880},
                         "unit": {"kind": "declared", "value": "count"},
                         "domain": "qualified_leaders"},
                        {"requirement_kind": "task",
                         "requirement_id": "assist_leader_2024_25",
                         "output_id": "PLAYER_NAME",
                         "node_id": "assist_leader_2024_25",
                         "evidence_id": evidence_id,
                         "selector": "rows[0].PLAYER_NAME",
                         "value": {"kind": "string",
                                   "value": "Trae Young"},
                         "unit": {"kind": "unitless"},
                         "domain": "qualified_leaders"},
                    ],
                }],
                "calculations": [],
                "blocked_calculation_requirement_ids": [],
                "gaps": [],
            }
            return TypeAdapter(schema).validate_json(json.dumps(draft))

    synth = ModelSynthesizer(
        StubModel(), provider="gemini",
        model_name="gemini-3.5-flash-lite")
    draft = asyncio.run(synth.synthesize(task, [envelope]))
    assert draft.claims[0].text.startswith("Trae Young led the NBA")
    assert [binding.requirement_id
            for binding in draft.claims[0].output_bindings] == [None, None]
    assert [binding.output_id
            for binding in draft.claims[0].output_bindings] == [
                "AST", "PLAYER_NAME"]


def test_task_scoped_claim_verifies_and_admits(warehouse):
    from v2.contracts import (
        Claim, ClaimKind, DraftReport, EvidenceOutputBinding,
        EvidenceRequirement, Plan, PlanNode, PlanStatus,
        SeasonRef, TaskSpec, VerifiedClaim,
    )
    from v2.runtime.models import (
        ExecutionResult, admit_verified_claim_bindings,
    )
    from v2.runtime.verifier import verify_mechanical
    envelope = call_capability(
        "qualified_leaders",
        {"stat_category": "AST", "season": SEASON})
    assert envelope.rows[0]["PLAYER_NAME"] == "Trae Young"
    task = TaskSpec(
        goal="Identify the player who led the NBA in assists during "
             "the 2024-25 season and report their assist total.",
        mode="quick",
        deliverable="The name of the assist leader for the 2024-25 NBA "
                    "season and their total number of assists.",
        metric_ids=["AST"],
        requested_outputs=["PLAYER_NAME", "AST"],
        season=SeasonRef(value=SEASON, source="user", confidence=1.0),
        requirements=[EvidenceRequirement(
            id="assist_leader_2024_25",
            description="Identify the player who led the NBA in assists "
                        "during the 2024-25 season and report their total.",
            capability_options=["qualified_leaders"],
            capability_arguments={
                "stat_category": "AST", "season": SEASON,
                "min_attempts": 0, "ranking_direction": "desc"},
            metric_ids=["AST"],
            requested_outputs=["PLAYER_NAME", "AST"])])
    plan = Plan(nodes=[PlanNode(
        id="leader", description="Fetch 2024-25 assists leaderboard",
        capability_hints=["qualified_leaders"],
        covers_requirement_ids=["assist_leader_2024_25"],
        arguments={"stat_category": "AST", "season": SEASON},
        status=PlanStatus.COMPLETE)])
    execution = ExecutionResult(
        plan=plan, evidence_by_node={"leader": envelope},
        attempts={"leader": 1})
    bindings = [
        EvidenceOutputBinding(
            requirement_kind="task",
            requirement_id=None, output_id="AST",
            node_id="leader", evidence_id=envelope.evidence_id,
            selector="rows[0].AST",
            value={"kind": "integer", "value": 880},
            unit={"kind": "declared", "value": "count"},
            domain="qualified_leaders"),
        EvidenceOutputBinding(
            requirement_kind="task",
            requirement_id=None, output_id="PLAYER_NAME",
            node_id="leader", evidence_id=envelope.evidence_id,
            selector="rows[0].PLAYER_NAME",
            value={"kind": "string", "value": "Trae Young"},
            unit={"kind": "unitless"},
            domain="qualified_leaders"),
    ]
    claim = Claim(
        text="Trae Young led the NBA with 880 assists in 76 games "
             "in 2024-25.",
        kind=ClaimKind.OBSERVED, evidence_ids=[envelope.evidence_id],
        output_bindings=bindings)
    draft = DraftReport(sections=["Assists leader"], claims=[claim], gaps=[])
    report = verify_mechanical(task, draft, [envelope])
    assert report.claim_results[0].supported is True
    candidate = VerifiedClaim(
        claim_index=0, claim=claim, evidence_ids=[envelope.evidence_id],
        sources=[{"evidence_id": envelope.evidence_id,
                  "source": envelope.source,
                  "capability": envelope.capability,
                  "observed_at": envelope.observed_at,
                  "as_of": envelope.as_of,
                  "vintages": dict(envelope.vintages)}],
        output_bindings=bindings)
    assert admit_verified_claim_bindings(
        task, execution, draft, candidate) is candidate


def test_planner_wire_entries_validate_without_null_value_slot():
    from v2.arguments import ProviderWireArguments, provider_to_source
    wire = ProviderWireArguments.model_validate({
        "entries": [
            {"key": "ranking_direction", "kind": "string",
             "string_value": ""},
            {"key": "requested_metric", "kind": "string",
             "string_value": ""},
            {"key": "season", "kind": "string",
             "string_value": "2024-25"},
            {"key": "team", "kind": "string", "string_value": "BOS"},
        ]})
    assert provider_to_source(
        wire, "planner", capability_id="team_ratings") == {
            "ranking_direction": "", "requested_metric": "",
            "season": "2024-25", "team": "BOS"}
