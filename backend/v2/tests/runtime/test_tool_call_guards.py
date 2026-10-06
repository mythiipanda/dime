from __future__ import annotations

from datetime import UTC, datetime

import pytest

from v2.contracts import EntityRef, Plan, PlanNode, RunMode, SeasonRef, TaskSpec
from v2.domain.evidence import post_result_denials, pre_call_denials
from v2.runtime import FakeCapability, PlanExecutor

@pytest.fixture
def anyio_backend():
    return "asyncio"

def _task(**overrides):
    base = dict(goal="answer", mode=RunMode.QUICK, deliverable="text")
    base.update(overrides)
    return TaskSpec(**base)

def _season_task(value="2025-26", **overrides):
    return _task(season=SeasonRef(value=value, source="user", confidence=1), **overrides)

class _Probe(FakeCapability):
    def __init__(self, name, rows, **kwargs):
        super().__init__(name, rows, **kwargs)
        self.calls = []

    async def execute(self, node, task, evidence):
        self.calls.append(node.id)
        return await super().execute(node, task, evidence)

class _FixedSeason:
    def __init__(self, name, season, rows=None, entities=None):
        self.name = name
        self.task_season_scoped = True
        self._season = season
        self._rows = rows if rows is not None else [{"PTS": 10}]
        self._entities = entities or []
        self.calls = []

    async def execute(self, node, task, evidence):
        self.calls.append(node.id)
        from v2.contracts import EvidenceEnvelope

        return EvidenceEnvelope(
            evidence_id=f"evidence:{node.id}",
            capability=self.name,
            source="fake",
            observed_at=datetime.now(UTC),
            season=self._season,
            entities=self._entities,
            rows=self._rows,
        )

class _FixedSubject:
    def __init__(self, name, entities, rows):
        self.name = name
        self.task_season_scoped = False
        self._entities = entities
        self._rows = rows
        self.calls = []

    async def execute(self, node, task, evidence):
        self.calls.append(node.id)
        from v2.contracts import EvidenceEnvelope

        return EvidenceEnvelope(
            evidence_id=f"evidence:{node.id}",
            capability=self.name,
            source="fake",
            observed_at=datetime.now(UTC),
            entities=self._entities,
            rows=self._rows,
        )

class _FixedEmpty:
    def __init__(self, name, scoped):
        self.name = name
        self.task_season_scoped = scoped
        self.calls = []

    async def execute(self, node, task, evidence):
        self.calls.append(node.id)
        from v2.contracts import EvidenceEnvelope

        return EvidenceEnvelope(
            evidence_id=f"evidence:{node.id}",
            capability=self.name,
            source="fake",
            observed_at=datetime.now(UTC),
            season=task.season.value if (task.season and self.task_season_scoped) else None,
            rows=[],
        )

def test_pre_call_denials_name_contradiction_without_execution():
    task = _season_task()
    denials = pre_call_denials(task, "standings", {"season": "2024-25"})
    assert len(denials) == 1
    assert denials[0].capability == "standings"
    assert denials[0].check == "season_mismatch"
    assert "2024-25" in denials[0].message
    assert "2025-26" in denials[0].message

@pytest.mark.anyio
async def test_season_outside_scope_refused_before_execution():
    probe = _Probe("standings", [{"WINS": 61}])
    task = _season_task()
    plan = Plan(nodes=[PlanNode(id="a", description="a", capability_hints=["standings"], arguments={"season": "2024-25"})])
    result = await PlanExecutor({"standings": probe}).execute(task, plan)
    assert probe.calls == []
    assert result.plan.nodes[0].status.value == "failed"
    assert "standings" in result.errors["a"][0]
    assert "season_mismatch" in result.errors["a"][0]

@pytest.mark.anyio
async def test_wrong_season_rows_refused_after_execution():
    cap = _FixedSeason("standings", "2024-25")
    task = _season_task()
    plan = Plan(nodes=[PlanNode(id="a", description="a", capability_hints=["standings"])])
    result = await PlanExecutor({"standings": cap}).execute(task, plan)
    assert cap.calls == ["a"]
    assert result.plan.nodes[0].status.value == "failed"
    assert "season_mismatch" in result.errors["a"][0]

@pytest.mark.anyio
async def test_right_rows_pass_both_guards():
    entities = [EntityRef(id="1610612738", type="team", display_name="Boston Celtics")]
    cap = _FixedSubject("team_ratings", entities, [{"TEAM_ID": "1610612738", "WINS": 61}])
    task = _task(entities=entities)
    plan = Plan(nodes=[PlanNode(id="a", description="a", capability_hints=["team_ratings"], arguments={"team_id": "1610612738"})])
    result = await PlanExecutor({"team_ratings": cap}).execute(task, plan)
    assert result.plan.nodes[0].status.value == "complete"
    assert result.evidence_by_node["a"].rows == [{"TEAM_ID": "1610612738", "WINS": 61}]

@pytest.mark.anyio
async def test_wrong_subject_rows_refused():
    wanted = [EntityRef(id="1610612738", type="team", display_name="Boston Celtics")]
    other = [EntityRef(id="1610612747", type="team", display_name="Los Angeles Lakers")]
    cap = _FixedSubject("team_ratings", other, [{"TEAM_ID": "1610612747", "WINS": 50}])
    task = _task(entities=wanted)
    plan = Plan(nodes=[PlanNode(id="a", description="a", capability_hints=["team_ratings"], arguments={"team_id": "1610612738"})])
    result = await PlanExecutor({"team_ratings": cap}).execute(task, plan)
    assert result.plan.nodes[0].status.value == "failed"
    assert "entity_mismatch" in result.errors["a"][0]

@pytest.mark.anyio
async def test_guards_run_on_every_capability_call():
    alpha = _Probe("alpha", [{"n": 1}])
    beta = _Probe("beta", [{"n": 1}])
    task = _season_task()
    plan = Plan(nodes=[
        PlanNode(id="a", description="a", capability_hints=["alpha"], arguments={"season": "2024-25"}),
        PlanNode(id="b", description="b", capability_hints=["beta"], arguments={"season": "2024-25"}),
    ])
    result = await PlanExecutor({"alpha": alpha, "beta": beta}).execute(task, plan)
    assert alpha.calls == []
    assert beta.calls == []
    assert result.plan.nodes[0].status.value == "failed"
    assert result.plan.nodes[1].status.value == "failed"
    assert "season_mismatch" in result.errors["a"][0]
    assert "season_mismatch" in result.errors["b"][0]
    assert "alpha" in result.errors["a"][0]
    assert "beta" in result.errors["b"][0]

def test_post_result_denials_pass_for_matching_scope():
    from v2.contracts import EvidenceEnvelope

    task = _season_task()
    envelope = EvidenceEnvelope(
        evidence_id="ev",
        capability="standings",
        source="fake",
        observed_at=datetime.now(UTC),
        season="2025-26",
        rows=[{"WINS": 61, "season": "2025-26"}],
    )
    assert post_result_denials(task, envelope) == []

def test_empty_forbidden_by_contract_fails_loud():
    from v2.contracts import EvidenceEnvelope

    task = _season_task()
    envelope = EvidenceEnvelope(
        evidence_id="ev",
        capability="sql_exec",
        source="fake",
        observed_at=datetime.now(UTC),
        season="2025-26",
        rows=[],
    )
    denials = post_result_denials(task, envelope)
    assert [item.check for item in denials] == ["empty_rows_forbidden"]
    assert denials[0].capability == "sql_exec"

def test_empty_allowed_by_contract_stays_allowed():
    from v2.contracts import EvidenceEnvelope

    task = _task()
    envelope = EvidenceEnvelope(
        evidence_id="ev",
        capability="injuries",
        source="fake",
        observed_at=datetime.now(UTC),
        rows=[],
    )
    assert post_result_denials(task, envelope) == []

@pytest.mark.anyio
async def test_empty_contract_enforced_on_every_call_path():
    sql = _FixedEmpty("sql_exec", True)
    task = _season_task()
    plan = Plan(nodes=[PlanNode(id="a", description="a", capability_hints=["sql_exec"])])
    result = await PlanExecutor({"sql_exec": sql}).execute(task, plan)
    assert result.plan.nodes[0].status.value == "failed"
    assert "empty_rows_forbidden" in result.errors["a"][0]
