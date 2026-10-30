from __future__ import annotations

from typing import Any, Mapping
import pytest
from v2.adapters.models import ModelPlanner
from v2.contracts import (
    Claim,
    ClaimKind,
    DraftReport,
    EvidenceRequirement,
    PeriodScope,
    PeriodScopeSource,
    Plan,
    PlanNode,
    PlanStatus,
    RunMode,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
)
from v2.runtime import FakeCapability, Runtime
from v2.runtime.executor import PlanExecutor, PlanValidationError
from v2.tests.runtime.test_model_stages import StubModel

@pytest.fixture
def anyio_backend():
    return "asyncio"

EXPECTED_CELTICS_SQL = (
    "SELECT COUNT(*) AS games, SUM(CASE WHEN wl = 'W' THEN 1 ELSE 0 END) AS wins, "
    "SUM(CASE WHEN wl = 'L' THEN 1 ELSE 0 END) AS losses, SUM(pts) AS total_points, "
    "CAST(SUM(pts) AS DOUBLE) / COUNT(*) AS mean_points_per_game "
    "FROM silver_hist_gamelogs WHERE _season = '2024-25' "
    "AND season_type = 'Regular Season' AND team_name = 'Boston Celtics'"
)

REPAIRED_CELTICS_SQL = (
    "SELECT COUNT(*) AS games, SUM(CASE WHEN wl = 'W' THEN 1 ELSE 0 END) AS wins, "
    "SUM(CASE WHEN wl = 'L' THEN 1 ELSE 0 END) AS losses, SUM(pts) AS total_points, "
    "CAST(SUM(pts) AS DOUBLE) / COUNT(*) AS mean_points_per_game "
    "FROM silver_hist_gamelogs WHERE _season = '2024-25' "
    "AND season_type = 'regular-season' AND team_name = 'Boston Celtics'"
)

def make_celtics_task() -> TaskSpec:
    return TaskSpec(
        goal="Report the Boston Celtics 2024-25 regular-season statistics.",
        mode=RunMode.QUICK,
        deliverable="text",
        period_scope=PeriodScope.REGULAR_SEASON,
        period_scope_source=PeriodScopeSource.EXPLICIT_REQUEST,
        required_evidence=["sql_exec"],
        requirements=[
            EvidenceRequirement(
                id="celtics_aggregation",
                description="Aggregate Boston Celtics regular-season rows from silver_hist_gamelogs.",
                capability_options=["sql_exec"],
                capability_arguments={"sql": EXPECTED_CELTICS_SQL},
            ),
        ],
    )

def make_sql_catalog() -> Mapping[str, Any]:
    return {
        "sql_exec": {
            "name": "sql_exec",
            "description": "execute sql",
            "arguments": {
                "type": "object",
                "required": ["sql"],
                "properties": {
                    "sql": {"type": "string"},
                },
            },
        },
    }

class RepairedSeasonPlanner:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    async def plan(self, task: TaskSpec, failure_context: Any = None) -> Plan:
        self.calls.append(failure_context)
        selected_sql = (
            REPAIRED_CELTICS_SQL
            if failure_context is not None
            else EXPECTED_CELTICS_SQL
        )
        return Plan(nodes=[
            PlanNode(
                id="query_node",
                description="query celtics",
                capability_hints=["sql_exec"],
                covers_requirement_ids=["celtics_aggregation"],
                arguments={"sql": selected_sql},
            )
        ])

class PersistentInvalidPlanner:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    async def plan(self, task: TaskSpec, failure_context: Any = None) -> Plan:
        self.calls.append(failure_context)
        return Plan(nodes=[
            PlanNode(
                id="query_node",
                description="query celtics",
                capability_hints=["sql_exec"],
                covers_requirement_ids=["celtics_aggregation"],
                arguments={"sql": EXPECTED_CELTICS_SQL},
            )
        ])

class CelticsIntake:
    def __init__(self, task: TaskSpec) -> None:
        self.task = task

    async def understand(self, request: str) -> TaskSpec:
        return self.task

class CelticsSynthesizer:
    async def synthesize(self, task: Any, evidence: Any) -> DraftReport:
        return DraftReport(
            sections=["Answer"],
            claims=[Claim(
                text="The Celtics won 61 games.",
                kind=ClaimKind.OBSERVED,
                evidence_ids=["evidence:query_node"],
            )],
        )

class PassVerifier:
    async def verify(self, task: Any, draft: Any, evidence: Any) -> VerificationReport:
        return VerificationReport(
            status=VerificationStatus.PASS,
            claim_results=[
                {"claim_index": claim_index, "supported": True}
                for claim_index, claim_item in enumerate(draft.claims)
            ],
        )

def make_model_planner() -> ModelPlanner:
    return ModelPlanner(
        StubModel([]),
        provider="stub",
        model_name="stub",
        capability_catalog=make_sql_catalog(),
    )

def test_model_planner_coverage_accepts_corrected_literal() -> None:
    planner = make_model_planner()
    task = make_celtics_task()
    candidate_plan = Plan(nodes=[
        PlanNode(
            id="query_node",
            description="query celtics",
            capability_hints=["sql_exec"],
            covers_requirement_ids=["celtics_aggregation"],
            arguments={"sql": REPAIRED_CELTICS_SQL},
        )
    ])
    normalized = planner._normalize_requirement_coverage(task, candidate_plan)
    assert normalized.nodes[0].covers_requirement_ids == ["celtics_aggregation"]

def test_model_planner_coverage_rejects_unrelated_select_one_and_wrong_team() -> None:
    planner = make_model_planner()
    task = make_celtics_task()

    select_one_plan = Plan(nodes=[
        PlanNode(
            id="query_node",
            description="query celtics",
            capability_hints=["sql_exec"],
            covers_requirement_ids=["celtics_aggregation"],
            arguments={"sql": "SELECT 1"},
        )
    ])
    select_one_normalized = planner._normalize_requirement_coverage(task, select_one_plan)
    assert select_one_normalized.nodes[0].covers_requirement_ids == []

    wrong_team_sql = REPAIRED_CELTICS_SQL.replace("Boston Celtics", "Miami Heat")
    wrong_team_plan = Plan(nodes=[
        PlanNode(
            id="query_node",
            description="query celtics",
            capability_hints=["sql_exec"],
            covers_requirement_ids=["celtics_aggregation"],
            arguments={"sql": wrong_team_sql},
        )
    ])
    wrong_team_normalized = planner._normalize_requirement_coverage(task, wrong_team_plan)
    assert wrong_team_normalized.nodes[0].covers_requirement_ids == []

    wrong_season_sql = REPAIRED_CELTICS_SQL.replace("2024-25", "2023-24")
    wrong_season_plan = Plan(nodes=[
        PlanNode(
            id="query_node",
            description="query celtics",
            capability_hints=["sql_exec"],
            covers_requirement_ids=["celtics_aggregation"],
            arguments={"sql": wrong_season_sql},
        )
    ])
    wrong_season_normalized = planner._normalize_requirement_coverage(task, wrong_season_plan)
    assert wrong_season_normalized.nodes[0].covers_requirement_ids == []

    wrong_projection_sql = (
        "SELECT pts FROM silver_hist_gamelogs WHERE _season = '2024-25' "
        "AND season_type = 'regular-season' AND team_name = 'Boston Celtics'"
    )
    wrong_proj_plan = Plan(nodes=[
        PlanNode(
            id="query_node",
            description="query celtics",
            capability_hints=["sql_exec"],
            covers_requirement_ids=["celtics_aggregation"],
            arguments={"sql": wrong_projection_sql},
        )
    ])
    wrong_proj_normalized = planner._normalize_requirement_coverage(task, wrong_proj_plan)
    assert wrong_proj_normalized.nodes[0].covers_requirement_ids == []

@pytest.mark.anyio
async def test_invalid_period_scope_plan_repairs_via_failure_context() -> None:
    task = make_celtics_task()
    planner = RepairedSeasonPlanner()
    runtime = Runtime(
        intake=CelticsIntake(task),
        planner=planner,
        executor=PlanExecutor({"sql_exec": FakeCapability("sql_exec", {"games": 82})}),
        synthesizer=CelticsSynthesizer(),
        mechanical_verifier=PassVerifier(),
        semantic_verifier=PassVerifier(),
    )
    result = await runtime.run("Report the Boston Celtics 2024-25 regular-season statistics.")
    assert result.verification.status == VerificationStatus.PASS
    assert len(planner.calls) == 2
    assert planner.calls[0] is None
    assert "period scope requires silver_hist_gamelogs.season_type = 'regular-season'" in str(planner.calls[1])
    assert result.execution.plan.nodes[0].arguments["sql"] == REPAIRED_CELTICS_SQL
    assert result.execution.plan.nodes[0].status == PlanStatus.COMPLETE

@pytest.mark.anyio
async def test_persistent_invalid_plan_fails_loud_without_executing_bad_plan() -> None:
    task = make_celtics_task()
    planner = PersistentInvalidPlanner()
    execution_counter = {"executed": 0}

    class CountingCapability(FakeCapability):
        async def execute(self, node: Any, evidence_by_node: Any, run_id: Any = None) -> Any:
            execution_counter["executed"] += 1
            return await super().execute(node, evidence_by_node, run_id)

    runtime = Runtime(
        intake=CelticsIntake(task),
        planner=planner,
        executor=PlanExecutor({"sql_exec": CountingCapability("sql_exec", {"games": 82})}),
        synthesizer=CelticsSynthesizer(),
        mechanical_verifier=PassVerifier(),
        semantic_verifier=PassVerifier(),
    )
    with pytest.raises(PlanValidationError, match="period scope requires"):
        await runtime.run("Report the Boston Celtics 2024-25 regular-season statistics.")
    assert len(planner.calls) == 2
    assert execution_counter["executed"] == 0

@pytest.mark.anyio
async def test_model_planner_attaches_bounded_feedback_from_failure_context() -> None:
    task = make_celtics_task()
    catalog = make_sql_catalog()
    stub = StubModel([{
        "nodes": [{
            "id": "query_node",
            "description": "query celtics",
            "capability": "sql_exec",
            "covers_requirement_ids": ["celtics_aggregation"],
            "arguments": {"sql": REPAIRED_CELTICS_SQL},
        }]
    }])
    planner = ModelPlanner(
        stub,
        provider="stub",
        model_name="stub",
        capability_catalog=catalog,
    )
    planner._catalog_for = lambda current_task: catalog
    failure_message = (
        "period scope requires silver_hist_gamelogs.season_type = "
        "'regular-season' in its source scope"
    )
    plan = await planner.plan(task, failure_context={"plan_error": failure_message})

    assert len(stub.calls) == 1
    call_payload = stub.calls[0].get("payload", {})
    feedback = call_payload.get("coverage_feedback")
    assert feedback is not None
    assert feedback.get("invalid_arguments") == failure_message
    assert feedback.get("instruction") == "Return a complete replacement plan."
    assert plan.nodes[0].arguments["sql"] == REPAIRED_CELTICS_SQL


R5_CAPTURED_CELTICS_SQL = (
    "SELECT Team_ID, COUNT(*) AS games_played, "
    "SUM(CASE WHEN WL = 'W' THEN 1 ELSE 0 END) AS wins, "
    "SUM(CASE WHEN WL = 'L' THEN 1 ELSE 0 END) AS losses, "
    "SUM(PTS) AS total_points_scored, "
    "CAST(SUM(PTS) AS DOUBLE) / COUNT(*) AS mean_points_per_game "
    "FROM silver_team_games WHERE _season = '2024-25' "
    "AND Team_ID = (SELECT TeamID FROM silver_standings WHERE TeamName = "
    "'Boston Celtics' LIMIT 1) GROUP BY Team_ID"
)

class CapturedR5Planner:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    async def plan(self, task: TaskSpec, failure_context: Any = None) -> Plan:
        self.calls.append(failure_context)
        selected_sql = (
            REPAIRED_CELTICS_SQL
            if failure_context is not None
            else R5_CAPTURED_CELTICS_SQL
        )
        return Plan(nodes=[
            PlanNode(
                id="query_node",
                description="query celtics",
                capability_hints=["sql_exec"],
                covers_requirement_ids=["celtics_aggregation"],
                arguments={"sql": selected_sql},
            )
        ])

R507_PLAYER_EXPECTED = (
    "SELECT PLAYER, TEAM, GP, PPG, RPG, APG, TS_PCT FROM silver_player_season "
    "WHERE PLAYER = 'Shai Gilgeous-Alexander' AND _season = '2024-25'"
)
R507_PLAYER_ALIASED = (
    "SELECT PLAYER, TEAM, GP, PPG, RPG, APG, TS_PCT, PPG AS \"PTS\", "
    "RPG AS \"REB\", APG AS \"AST\" FROM silver_player_season "
    "WHERE PLAYER = 'Shai Gilgeous-Alexander' AND _season = '2024-25'"
)
R507_HIST_EXPECTED = (
    "SELECT player_name, team_abbreviation, gp, pts, reb, ast "
    "FROM silver_hist_player_seasons WHERE player_name = "
    "'Shai Gilgeous-Alexander' AND _season = '2024-25'"
)
R507_HIST_ALIASED = (
    "SELECT player_name, team_abbreviation, gp AS \"GP\", pts AS \"TOTAL_PTS\", "
    "reb AS \"TOTAL_REB\", ast AS \"TOTAL_AST\", pts AS \"PTS\", reb AS \"REB\", "
    "ast AS \"AST\" FROM silver_hist_player_seasons WHERE player_name = "
    "'Shai Gilgeous-Alexander' AND _season = '2024-25'"
)


def test_shared_sql_coverage_keeps_renamed_source_columns() -> None:
    from v2.domain.sql_coverage import sql_covers

    aliased_only = (
        "SELECT player_name, team_abbreviation, gp AS \"GP\", "
        "pts AS \"TOTAL_PTS\", reb AS \"TOTAL_REB\", ast AS \"TOTAL_AST\" "
        "FROM silver_hist_player_seasons WHERE player_name = "
        "'Shai Gilgeous-Alexander' AND _season = '2024-25'"
    )
    assert sql_covers(R507_HIST_EXPECTED, aliased_only)


R512_SCOPE_EXPECTED = (
    "SELECT PLAYER, TEAM, PPG FROM silver_player_season "
    "WHERE PLAYER = 'PlayerA' AND TEAM = 'BOS' AND _season = '2024-25'"
)
R512_SCOPE_ALIASED = (
    "SELECT PLAYER, TEAM, PPG, PPG AS \"PTS\" FROM silver_player_season "
    "WHERE PLAYER = 'PlayerA' AND TEAM = 'BOS' AND _season = '2024-25'"
)


@pytest.mark.parametrize("actual", [
    R512_SCOPE_EXPECTED.replace("'PlayerA'", "'playera'"),
    R512_SCOPE_EXPECTED.replace("'PlayerA'", "'PLAYERA'"),
    R512_SCOPE_EXPECTED.replace("'BOS'", "'bos'"),
    R512_SCOPE_EXPECTED.replace("'2024-25'", "'2024-25 '"),
])
def test_shared_sql_coverage_preserves_literal_values(actual: str) -> None:
    from v2.domain.sql_coverage import sql_covers

    assert not sql_covers(R512_SCOPE_EXPECTED, actual)


def test_shared_sql_coverage_projection_extension_preserves_literals() -> None:
    from v2.domain.sql_coverage import sql_covers

    assert sql_covers(R512_SCOPE_EXPECTED, R512_SCOPE_ALIASED)
    for actual in (
        R512_SCOPE_ALIASED.replace("'PlayerA'", "'playera'"),
        R512_SCOPE_ALIASED.replace("'BOS'", "'bos'"),
        R512_SCOPE_ALIASED.replace("'2024-25'", "'2024-25 '"),
    ):
        assert not sql_covers(R512_SCOPE_EXPECTED, actual)


def test_shared_sql_coverage_accepts_identifier_and_alias_case() -> None:
    from v2.domain.sql_coverage import sql_covers

    assert sql_covers(
        R512_SCOPE_EXPECTED,
        "select player, team, ppg from SILVER_PLAYER_SEASON "
        "where PLAYER = 'PlayerA' and team = 'BOS' and _season = '2024-25'",
    )
    # Added projection takes the fallback path; alias case is insignificant.
    assert sql_covers(
        R512_SCOPE_EXPECTED,
        "select player, team, ppg, ppg as pts from SILVER_PLAYER_SEASON "
        "where PLAYER = 'PlayerA' and team = 'BOS' and _season = '2024-25'",
    )


def test_shared_sql_coverage_keeps_regular_season_literal_normalization() -> None:
    from v2.domain.sql_coverage import sql_covers

    expected = (
        "SELECT COUNT(*) AS games, MAX(pts) AS best FROM silver_hist_gamelogs "
        "WHERE season_type = 'Regular Season' AND team_name = 'Boston Celtics'"
    )
    assert sql_covers(
        expected, expected.replace("'Regular Season'", "'regular-season'"))
    assert sql_covers(
        expected, expected.replace("'Regular Season'", "'REGULAR SEASON'"))


def make_r507_alias_task() -> TaskSpec:
    return TaskSpec(
        goal="SGA per-game and totals.",
        mode=RunMode.QUICK,
        deliverable="text",
        required_evidence=["sql_exec"],
        requirements=[
            EvidenceRequirement(
                id="per_game_from_player_season",
                description="per game",
                capability_options=["sql_exec"],
                capability_arguments={"sql": R507_PLAYER_EXPECTED},
                requested_outputs=["PPG", "RPG", "APG", "TS_PCT"],
            ),
            EvidenceRequirement(
                id="cumulative_totals_from_hist_player_seasons",
                description="totals",
                capability_options=["sql_exec"],
                capability_arguments={"sql": R507_HIST_EXPECTED},
                requested_outputs=["TOTAL_PTS", "TOTAL_REB", "TOTAL_AST"],
            ),
        ],
    )


def test_model_planner_coverage_accepts_direct_column_alias_superset() -> None:
    planner = make_model_planner()
    plan = Plan(nodes=[
        PlanNode(
            id="player", description="per game",
            capability_hints=["sql_exec"],
            covers_requirement_ids=["per_game_from_player_season"],
            arguments={"sql": R507_PLAYER_ALIASED},
        ),
        PlanNode(
            id="hist", description="totals",
            capability_hints=["sql_exec"],
            covers_requirement_ids=[
                "cumulative_totals_from_hist_player_seasons"],
            arguments={"sql": R507_HIST_ALIASED},
        ),
    ])
    normalized = planner._normalize_requirement_coverage(
        make_r507_alias_task(), plan)
    assert [node.covers_requirement_ids for node in normalized.nodes] == [
        ["per_game_from_player_season"],
        ["cumulative_totals_from_hist_player_seasons"],
    ]


@pytest.mark.parametrize("sql", [
    # different team / season / filter scope
    R507_PLAYER_ALIASED.replace("Shai Gilgeous-Alexander", "Jayson Tatum"),
    R507_PLAYER_ALIASED.replace("2024-25", "2023-24"),
    R507_PLAYER_ALIASED + " AND PPG > 10",
    # different source table
    R507_PLAYER_ALIASED.replace("silver_player_season", "silver_other_season"),
    # original source column dropped entirely
    "SELECT PLAYER, TEAM, GP, PPG, APG, TS_PCT, PPG AS \"PTS\", APG AS \"AST\" "
    "FROM silver_player_season WHERE PLAYER = 'Shai Gilgeous-Alexander' "
    "AND _season = '2024-25'",
    # aggregate / expression substitution
    R507_PLAYER_ALIASED.replace("PPG AS \"PTS\"", "SUM(PPG) AS \"PTS\""),
    R507_PLAYER_ALIASED.replace("PPG AS \"PTS\"", "ROUND(PPG, 1) AS \"PTS\""),
    # subquery / CTE / join scope
    R507_PLAYER_ALIASED + " AND PPG > (SELECT 1)",
    "WITH src AS (" + R507_PLAYER_EXPECTED + ") SELECT PLAYER, TEAM, GP, PPG, "
    "RPG, APG, TS_PCT, PPG AS \"PTS\" FROM src",
    R507_PLAYER_ALIASED.replace(
        "FROM silver_player_season",
        "FROM silver_player_season JOIN silver_hist_player_seasons "
        "ON silver_player_season.PLAYER = silver_hist_player_seasons.player_name"),
    R507_PLAYER_ALIASED.replace(
        "FROM silver_player_season",
        "FROM silver_player_season CROSS JOIN silver_hist_player_seasons"),
    # union scope
    R507_PLAYER_ALIASED + " UNION SELECT PLAYER, TEAM, GP, PPG, RPG, APG, "
    "TS_PCT, PPG, RPG, APG FROM silver_player_season",
    # group / order / limit / distinct drift
    R507_PLAYER_ALIASED + " GROUP BY PLAYER",
    R507_PLAYER_ALIASED + " ORDER BY PPG",
    R507_PLAYER_ALIASED + " LIMIT 1",
    R507_PLAYER_ALIASED.replace("SELECT ", "SELECT DISTINCT ", 1),
    # wildcard is not a direct-column identity
    "SELECT *, PPG AS \"PTS\" FROM silver_player_season WHERE PLAYER = "
    "'Shai Gilgeous-Alexander' AND _season = '2024-25'",
])
def test_model_planner_coverage_rejects_direct_column_scope_or_expression_drift(
    sql: str,
) -> None:
    planner = make_model_planner()
    plan = Plan(nodes=[PlanNode(
        id="player", description="per game",
        capability_hints=["sql_exec"],
        covers_requirement_ids=["per_game_from_player_season"],
        arguments={"sql": sql},
    )])
    normalized = planner._normalize_requirement_coverage(
        make_r507_alias_task(), plan)
    assert normalized.nodes[0].covers_requirement_ids == []


@pytest.mark.anyio
async def test_captured_r5_source_scope_failure_provides_server_constraint_and_repairs() -> None:
    task = make_celtics_task()
    planner = CapturedR5Planner()
    runtime = Runtime(
        intake=CelticsIntake(task),
        planner=planner,
        executor=PlanExecutor({"sql_exec": FakeCapability("sql_exec", {"games": 82})}),
        synthesizer=CelticsSynthesizer(),
        mechanical_verifier=PassVerifier(),
        semantic_verifier=PassVerifier(),
    )
    result = await runtime.run("Report the Boston Celtics 2024-25 regular-season statistics.")
    assert result.verification.status == VerificationStatus.PASS
    assert len(planner.calls) == 2
    assert planner.calls[0] is None
    assert "period scope requires silver_hist_gamelogs.season_type = 'regular-season'" in str(planner.calls[1])
    assert result.execution.plan.nodes[0].arguments["sql"] == REPAIRED_CELTICS_SQL
    assert result.execution.plan.nodes[0].status == PlanStatus.COMPLETE
