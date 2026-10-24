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
