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
            "CREATE TABLE silver_boxscores (GAME_ID VARCHAR, "
            "TEAM_ID BIGINT, teamTricode VARCHAR, teamCity VARCHAR, "
            "teamName VARCHAR, PLAYER_ID BIGINT, firstName VARCHAR, "
            "familyName VARCHAR, points BIGINT, "
            "fieldGoalsAttempted BIGINT, freeThrowsAttempted BIGINT, "
            "reboundsOffensive BIGINT, turnovers BIGINT, comment VARCHAR, "
            "_source VARCHAR, _season VARCHAR, _fetched_at VARCHAR, "
            "_entity VARCHAR)"
        )
        games = [
            ("0022400001", 1610612738, "BOS", "Boston", "Celtics",
             1, "Jay", "Star", 20, 10, 2, 1, 2, ""),
            ("0022400001", 1610612738, "BOS", "Boston", "Celtics",
             2, "Jay", "Sidekick", 80, 60, 10, 5, 8, ""),
            ("0022400001", 1610612752, "NYK", "New York", "Knicks",
             3, "Knick", "Leader", 90, 70, 10, 8, 12, ""),
            ("0022400002", 1610612738, "BOS", "Boston", "Celtics",
             1, "Jay", "Star", 60, 40, 4, 2, 5, ""),
            ("0022400002", 1610612738, "BOS", "Boston", "Celtics",
             2, "Jay", "Sidekick", 50, 35, 4, 2, 4, ""),
            ("0022400002", 1610612752, "NYK", "New York", "Knicks",
             3, "Knick", "Leader", 95, 72, 12, 6, 11, ""),
            ("0022400001", 1610612738, "BOS", "Boston", "Celtics",
             9, "Did", "Notplay", 500, 200, 100, 50, 60,
             "DND - Injury/Illness"),
            ("0042400101", 1610612738, "BOS", "Boston", "Celtics",
             1, "Jay", "Star", 200, 150, 40, 10, 20, ""),
            ("0042400101", 1610612752, "NYK", "New York", "Knicks",
             3, "Knick", "Leader", 190, 140, 30, 12, 18, ""),
        ]
        for game in games:
            connection.execute(
                "INSERT INTO silver_boxscores VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "'nba_stats', '2024-25', '2025-06-01T00:00:00+00:00', '')",
                list(game),
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
    assert row["OFF_RATING"] == 129.0
    assert row["DEF_RATING"] == 115.1
    assert row["NET_RATING"] == 13.9
    assert row["PACE"] == 81.4


def test_team_ratings_capability_binds_gamelog_fallback(warehouse):
    envelope = call_capability(
        "team_ratings", {"season": SEASON, "team": "Celtics"})
    assert envelope.season == SEASON
    assert envelope.rows[0]["NET_RATING"] == 13.9
    assert envelope.units["NET_RATING"] == "points_per_100_possessions"
    admit_evidence(envelope, required_season=SEASON)


def test_ratings_refusal_preserved_without_gamelogs(warehouse):
    result = get_ratings.invoke({"season": "2023-24", "team": "BOS"})
    assert result["ok"] is False
    assert result["rows"] == []


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
        text="The Boston Celtics had a net rating of 13.9, an offensive "
             "rating of 129.0, and a defensive rating of 115.1 "
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
