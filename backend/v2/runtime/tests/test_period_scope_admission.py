import pytest

from v2.contracts import PeriodScope, PeriodScopeSource, Plan, PlanNode, TaskSpec
from v2.runtime.executor import PlanExecutor, PlanValidationError

R20_SQL = (
    "SELECT COUNT(*) AS GAMES, SUM(W) AS WINS, SUM(L) AS LOSSES, "
    "SUM(PTS) AS PTS, AVG(PTS) AS PPG FROM silver_team_games "
    "WHERE _season = '2024-25' AND Team_ID = 1610612738"
)
R21_SQL = (
    "WITH celtics_games AS (SELECT game_id, "
    "MAX(CASE WHEN wl = 'W' THEN 1 ELSE 0 END) AS is_win, "
    "SUM(pts) AS game_points FROM silver_hist_gamelogs "
    "WHERE _season = '2024-25' AND team_abbreviation = 'BOS' "
    "GROUP BY game_id) SELECT COUNT(*) AS GAMES, SUM(is_win) AS WINS, "
    "SUM(1 - is_win) AS LOSSES, SUM(game_points) AS TOTAL_POINTS "
    "FROM celtics_games"
)


class _SqlCapability:
    name = "sql_exec"
    task_season_scoped = False

    def __init__(self):
        self.calls = 0

    def validate_arguments(self, node):
        assert isinstance(node.arguments.get("sql"), str)

    async def execute(self, node, task, evidence):
        self.calls += 1
        raise AssertionError("period-invalid SQL reached the capability")


def _task(scope=PeriodScope.REGULAR_SEASON):
    return TaskSpec(
        goal="team record",
        mode="quick",
        deliverable="record",
        period_scope=scope,
        period_scope_source=(
            PeriodScopeSource.DEFAULT
            if scope == PeriodScope.UNSPECIFIED
            else PeriodScopeSource.EXPLICIT_REQUEST
        ),
    )

@pytest.fixture
def anyio_backend():
    return "asyncio"


def _plan(sql):
    return Plan(nodes=[PlanNode(
        id="query",
        description="read team games",
        capability_hints=["sql_exec"],
        arguments={"sql": sql},
    )])


def _cte_sql(predicate=None):
    where = f" WHERE {predicate}" if predicate else ""
    return (
        "WITH selected_games AS ("
        "SELECT game_id FROM silver_hist_gamelogs" + where + ") "
        "SELECT COUNT(*) AS GAMES FROM selected_games"
    )


def test_plan_boundary_accepts_period_filter_in_physical_cte_scope():
    executor = PlanExecutor({"sql_exec": _SqlCapability()})
    executor.validate_plan(
        _task(), _plan(_cte_sql("season_type = 'regular-season'")))


def test_plan_boundary_accepts_playoff_filter_in_physical_scope():
    executor = PlanExecutor({"sql_exec": _SqlCapability()})
    executor.validate_plan(
        _task(PeriodScope.PLAYOFFS),
        _plan(_cte_sql("season_type = 'playoffs'")),
    )


@pytest.mark.parametrize(("scope", "sql"), [
    (PeriodScope.REGULAR_SEASON, _cte_sql()),
    (PeriodScope.REGULAR_SEASON, _cte_sql("season_type = 'playoffs'")),
    (PeriodScope.REGULAR_SEASON,
     _cte_sql("season_type IN ('regular-season', 'playoffs')")),
    (PeriodScope.PLAYOFFS, _cte_sql("season_type = 'regular-season'")),
])
def test_plan_boundary_rejects_missing_or_wrong_period_filter(scope, sql):
    executor = PlanExecutor({"sql_exec": _SqlCapability()})
    with pytest.raises(PlanValidationError, match="period scope"):
        executor.validate_plan(_task(scope), _plan(sql))


@pytest.mark.parametrize("sql", [R20_SQL, R21_SQL])
def test_captured_r20_r21_queries_without_period_filter_are_rejected(sql):
    executor = PlanExecutor({"sql_exec": _SqlCapability()})
    with pytest.raises(PlanValidationError, match="period scope"):
        executor.validate_plan(_task(), _plan(sql))


def test_outer_filter_does_not_cover_physical_cte_source():
    sql = (
        "WITH selected_games AS ("
        "SELECT game_id FROM silver_hist_gamelogs) "
        "SELECT COUNT(*) AS GAMES FROM selected_games "
        "WHERE season_type = 'regular-season'"
    )
    executor = PlanExecutor({"sql_exec": _SqlCapability()})
    with pytest.raises(PlanValidationError, match="period scope"):
        executor.validate_plan(_task(), _plan(sql))


@pytest.mark.parametrize("scope", [PeriodScope.ALL, PeriodScope.UNSPECIFIED])
def test_all_and_unspecified_keep_existing_sql_admission(scope):
    executor = PlanExecutor({"sql_exec": _SqlCapability()})
    executor.validate_plan(_task(scope), _plan(_cte_sql()))


def test_existing_plan_feedback_can_accept_corrected_candidate():
    executor = PlanExecutor({"sql_exec": _SqlCapability()})
    with pytest.raises(PlanValidationError):
        executor.validate_plan(_task(), _plan(_cte_sql()))
    executor.validate_plan(
        _task(), _plan(_cte_sql("season_type = 'regular-season'")))


@pytest.mark.anyio
async def test_execution_boundary_rejects_before_capability_call():
    capability = _SqlCapability()
    executor = PlanExecutor({"sql_exec": capability})
    with pytest.raises(ValueError, match="period scope"):
        await executor.execute(_task(), _plan(_cte_sql()))
    assert capability.calls == 0


def test_unknown_period_source_fails_closed_at_plan_boundary():
    executor = PlanExecutor({"sql_exec": _SqlCapability()})
    sql = "SELECT COUNT(*) FROM silver_team_games"
    with pytest.raises(PlanValidationError, match="period scope"):
        executor.validate_plan(_task(), _plan(sql))
