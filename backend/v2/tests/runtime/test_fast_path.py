from __future__ import annotations

from datetime import UTC, datetime

import pytest

from v2.contracts import (
    Claim,
    ClaimKind,
    DraftReport,
    EntityRef,
    EvidenceEnvelope,
    EvidenceOutputBinding,
    EvidenceRequirement,
    Plan,
    PlanNode,
    RunMode,
    SeasonRef,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
)
from v2.runtime import FakeCapability, PlanExecutor, Runtime
from v2.runtime.assembly import MechanicalVerifier
from v2.runtime.fast_path import is_fast_path_eligible


@pytest.fixture
def anyio_backend():
    return "asyncio"


class CountingModel:
    def __init__(self, task: TaskSpec, claim: Claim | None = None) -> None:
        self.task = task
        self.claim = claim
        self.calls: list[str] = []

    async def understand(self, request: str, context=()) -> TaskSpec:
        self.calls.append("intake")
        return self.task

    async def plan(self, task: TaskSpec, failure_context=None) -> Plan:
        self.calls.append("planner")
        requirement = task.requirements[0]
        return Plan(nodes=[PlanNode(
            id="n1",
            description=requirement.description,
            capability_hints=list(requirement.capability_options),
            covers_requirement_ids=[requirement.id],
            arguments=dict(requirement.capability_arguments),
        )])

    async def synthesize(self, task, evidence) -> DraftReport:
        self.calls.append("synthesizer")
        if self.claim is not None:
            return DraftReport(sections=["Answer"], claims=[self.claim])
        items = list(evidence.values()) if isinstance(evidence, dict) else list(evidence)
        envelope = items[0]
        row = envelope.rows[0] if isinstance(envelope.rows, list) else envelope.rows
        total = int(row["AST"])
        node_id = envelope.evidence_id.removeprefix("evidence:")
        return DraftReport(sections=["Answer"], claims=[Claim(
            text=f"Ada Vega led the league with {total} assists.",
            kind=ClaimKind.OBSERVED,
            evidence_ids=[envelope.evidence_id],
            output_bindings=[EvidenceOutputBinding(
                requirement_kind="evidence",
                requirement_id=task.requirements[0].id,
                output_id="AST",
                node_id=node_id,
                evidence_id=envelope.evidence_id,
                selector="rows[0].AST",
                row_selector="rows[0]",
                value={"kind": "integer", "value": total},
                subject_entity_type="player",
                subject_entity_id="9001",
                subject_selector="rows[0].PLAYER_ID",
                unit={"kind": "declared", "value": "count"},
                domain="qualified_leaders",
            )],
        )])

    async def verify(self, task, draft, evidence) -> VerificationReport:
        self.calls.append("semantic")
        return VerificationReport(
            status=VerificationStatus.PASS,
            claim_results=[
                {"claim_index": index, "supported": True}
                for index, _claim in enumerate(draft.claims)
            ],
        )

    async def repair(self, task, draft, evidence, verification) -> DraftReport:
        self.calls.append("repair")
        return draft


def _task_single() -> TaskSpec:
    return TaskSpec(
        goal="single fact lookup",
        mode=RunMode.QUICK,
        deliverable="leader and total",
        requested_outputs=["AST"],
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[EntityRef(id="9001", type="player", display_name="Ada Vega")],
        requirements=[EvidenceRequirement(
            id="leader",
            description="assists leaderboard",
            capability_options=["qualified_leaders"],
            capability_arguments={"stat_category": "AST"},
            requested_outputs=["AST"],
        )],
    )


def _task_comparison() -> TaskSpec:
    return TaskSpec(
        goal="comparison lookup",
        mode=RunMode.QUICK,
        deliverable="compare two players",
        requested_outputs=["AST"],
        entities=[
            EntityRef(id="9001", type="player", display_name="Ada Vega"),
            EntityRef(id="9002", type="player", display_name="Bram Kessler"),
        ],
        requirements=[EvidenceRequirement(
            id="leader",
            description="assists leaderboard",
            capability_options=["qualified_leaders"],
            requested_outputs=["AST"],
        )],
    )


def _task_brief() -> TaskSpec:
    return TaskSpec(
        goal="brief lookup",
        mode=RunMode.QUICK,
        deliverable="brief",
        entities=[EntityRef(id="9001", type="player", display_name="Ada Vega")],
        requirements=[
            EvidenceRequirement(
                id="one",
                description="first requirement",
                capability_options=["qualified_leaders"],
            ),
            EvidenceRequirement(
                id="two",
                description="second requirement",
                capability_options=["standings"],
            ),
        ],
    )


def _claim() -> Claim:
    return Claim(
        text="Ada Vega led the league with 880 assists.",
        kind=ClaimKind.OBSERVED,
        evidence_ids=["evidence:n1"],
        output_bindings=[EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id="leader",
            output_id="AST",
            node_id="n1",
            evidence_id="evidence:n1",
            selector="rows[0].AST",
            value={"kind": "integer", "value": 880},
            unit={"kind": "declared", "value": "count"},
            domain="qualified_leaders",
        )],
    )


def _runtime(model: CountingModel, rows) -> Runtime:
    return Runtime(
        intake=model,
        planner=model,
        executor=PlanExecutor({"qualified_leaders": FakeCapability("qualified_leaders", rows)}),
        synthesizer=model,
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=model,
        repairer=model,
    )


def _slow_runtime(model: CountingModel, rows) -> Runtime:
    return Runtime(
        intake=model,
        planner=model,
        executor=PlanExecutor({"qualified_leaders": FakeCapability("qualified_leaders", rows)}),
        synthesizer=model,
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=model,
        repairer=model,
        fast_path=False,
    )


def test_gate_uses_shape_only() -> None:
    assert is_fast_path_eligible(_task_single()) is True
    assert is_fast_path_eligible(_task_comparison()) is False
    assert is_fast_path_eligible(_task_brief()) is False


def test_gate_ignores_question_text() -> None:
    base = _task_single()
    altered = base.model_copy(update={"goal": "totally different wording here"})
    assert is_fast_path_eligible(altered) is True


@pytest.mark.anyio
async def test_single_fact_uses_fast_path_with_fewer_model_calls() -> None:
    rows = [{"PLAYER_ID": 9001, "PLAYER_NAME": "Ada Vega", "AST": 880}]
    model = CountingModel(_task_single())
    result = await _runtime(model, rows).run("single fact lookup")
    assert [item.status for item in result.output_statuses] == ["complete", "complete"]
    assert result.verified_claims[0].claim.text == "Ada Vega led the league with 880 assists."
    assert sorted(model.calls) == ["intake", "synthesizer"]
    assert len(model.calls) == 2


@pytest.mark.anyio
async def test_comparison_takes_full_loop() -> None:
    rows = [{"PLAYER_ID": 9001, "PLAYER_NAME": "Ada Vega", "AST": 880}]
    model = CountingModel(_task_comparison(), Claim(
        text="Ada Vega led with 880 assists.",
        kind=ClaimKind.OBSERVED,
        evidence_ids=["evidence:n1"],
    ))
    result = await _runtime(model, rows).run("comparison lookup")
    assert "planner" in model.calls
    assert "semantic" in model.calls
    assert len(model.calls) > 2
    assert result.verified_claims != [] or result.gaps != []


@pytest.mark.anyio
async def test_unverifiable_fast_path_falls_back_and_answers() -> None:
    rows = [{"PLAYER_ID": 9001, "PLAYER_NAME": "Ada Vega", "AST": 880}]
    bad = Claim(
        text="Ada Vega led the league with 1 assists.",
        kind=ClaimKind.OBSERVED,
        evidence_ids=["evidence:n1"],
    )
    model = CountingModel(_task_single(), bad)
    result = await _runtime(model, rows).run("single fact lookup")
    assert "planner" in model.calls
    assert model.calls.count("synthesizer") == 2
    assert result.verified_claims != [] or result.gaps != []


@pytest.mark.anyio
async def test_citation_completeness_matches_between_paths() -> None:
    rows = [{"PLAYER_ID": 9001, "PLAYER_NAME": "Ada Vega", "AST": 880}]
    fast_model = CountingModel(_task_single())
    fast_result = await _runtime(fast_model, rows).run("single fact lookup")
    slow_model = CountingModel(_task_single())
    slow_result = await _slow_runtime(slow_model, rows).run("single fact lookup")
    assert [item.status for item in fast_result.output_statuses] == [
        item.status for item in slow_result.output_statuses
    ]
    assert len(fast_result.verified_claims) == len(slow_result.verified_claims)


@pytest.mark.anyio
async def test_missing_data_zero_never_publishes_through_fast_shape() -> None:
    from v2.runtime.assembly import MechanicalVerifier as AssembledMechanical

    player = EntityRef(id="9999", type="player", display_name="Test Player")
    task = TaskSpec(
        goal="season scoring average",
        mode=RunMode.QUICK,
        deliverable="points per game",
        requested_outputs=["PPG"],
        entities=[player],
        season=SeasonRef(value="2025-26", source="user", confidence=1.0),
        requirements=[EvidenceRequirement(
            id="scoring",
            description="season scoring line",
            capability_options=["player_report"],
            requested_outputs=["PPG"],
        )],
    )
    assert is_fast_path_eligible(task) is True

    class Intake:
        async def understand(self, request: str, context=()) -> TaskSpec:
            return task

    class Planner:
        async def plan(self, task: TaskSpec, failure_context=None) -> Plan:
            return Plan(nodes=[PlanNode(
                id="scoring",
                description="season scoring line",
                capability_hints=["player_report"],
                covers_requirement_ids=["scoring"],
            )])

    class Synthesizer:
        async def synthesize(self, task, evidence):
            return DraftReport(sections=["Test Player averaged 0.0 points per game."], claims=[Claim(
                text="Test Player averaged 0.0 points per game in 2025-26.",
                kind=ClaimKind.OBSERVED,
                evidence_ids=["evidence:scoring"],
            )])

    class Semantic:
        async def verify(self, task, draft, evidence) -> VerificationReport:
            return VerificationReport(
                status=VerificationStatus.PASS,
                claim_results=[
                    {"claim_index": index, "supported": True}
                    for index, _claim in enumerate(draft.claims)
                ],
            )

    runtime = Runtime(
        intake=Intake(),
        planner=Planner(),
        executor=PlanExecutor({"player_report": FakeCapability("player_report", [
            {"PLAYER_ID": 9999, "PLAYER": "Test Player", "GP": 20, "PPG": 0.0},
        ])}),
        synthesizer=Synthesizer(),
        mechanical_verifier=AssembledMechanical(),
        semantic_verifier=Semantic(),
    )
    result = await runtime.run("season scoring average")
    assert result.verified_claims == []
    assert any("Test Player" in gap.message for gap in result.gaps)


@pytest.mark.anyio
async def test_real_warehouse_assists_leader_answers_through_fast_path(monkeypatch, tmp_path) -> None:
    import duckdb

    from shared import store
    from v2.adapters.core import ToolCapability

    warehouse = tmp_path / "fast_leaders.duckdb"
    connection = duckdb.connect(str(warehouse))
    connection.execute(
        "CREATE TABLE silver_leaders_ast (RANK BIGINT, PLAYER VARCHAR, "
        "TEAM VARCHAR, GP BIGINT, AST BIGINT, MIN BIGINT, _source VARCHAR, "
        "_season VARCHAR, _fetched_at VARCHAR)"
    )
    connection.execute(
        "INSERT INTO silver_leaders_ast VALUES (1, 'Real Star', 'DEN', "
        "65, 697, 2200, 'nba_stats', '2025-26', "
        "'2026-09-30T00:00:00+00:00')"
    )
    connection.execute(
        "CREATE TABLE silver_boxscores (PLAYER_ID BIGINT, firstName VARCHAR, "
        "familyName VARCHAR, GAME_ID VARCHAR, teamTricode VARCHAR, "
        "assists BIGINT, comment VARCHAR, _source VARCHAR, _season VARCHAR, "
        "_fetched_at VARCHAR, _entity VARCHAR)"
    )
    connection.close()
    monkeypatch.setattr(store, "DB_PATH", warehouse)
    store.warehouse_identity_cache_clear()

    task = TaskSpec(
        goal="real assists leader lookup",
        mode=RunMode.QUICK,
        deliverable="assists leader and total",
        requested_outputs=[],
        season=SeasonRef(value="2025-26", source="user", confidence=1.0),
        requirements=[EvidenceRequirement(
            id="assists_board",
            description="2025-26 assists leaderboard",
            capability_options=["qualified_leaders"],
            capability_arguments={"stat_category": "AST", "season": "2025-26"},
            requested_outputs=["AST"],
        )],
    )
    envelope_holder: dict = {}

    class WarehouseSynthesizer:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def synthesize(self, task, evidence):
            self.calls.append("synthesizer")
            envelope = list(evidence)[0] if isinstance(evidence, dict) else evidence[0]
            envelope_holder["envelope"] = envelope
            top = envelope.rows[0]
            total = int(top["AST"])
            name = str(top["PLAYER"])
            text = f"{name} led the league with {total} assists."
            claim = Claim(
                text=text,
                kind=ClaimKind.OBSERVED,
                evidence_ids=[envelope.evidence_id],
                output_bindings=[EvidenceOutputBinding(
                    requirement_kind="evidence",
                    requirement_id="assists_board",
                    output_id="AST",
                    node_id="fast",
                    evidence_id=envelope.evidence_id,
                    selector="rows[0].AST",
                    value={"kind": "integer", "value": total},
                    unit={"kind": "declared", "value": "count"},
                    domain="qualified_leaders",
                )],
            )
            return DraftReport(sections=["Answer"], claims=[claim])

    class Intake:
        async def understand(self, request: str, context=()) -> TaskSpec:
            return task

    class Planner:
        def __init__(self) -> None:
            self.calls = 0

        async def plan(self, task: TaskSpec, failure_context=None) -> Plan:
            self.calls += 1
            return Plan(nodes=[PlanNode(
                id="slow",
                description="slow leaderboard fetch",
                capability_hints=["qualified_leaders"],
                covers_requirement_ids=["assists_board"],
                arguments={"stat_category": "AST", "season": "2025-26"},
            )])

    class Semantic:
        async def verify(self, task, draft, evidence) -> VerificationReport:
            return VerificationReport(
                status=VerificationStatus.PASS,
                claim_results=[
                    {"claim_index": index, "supported": True}
                    for index, _claim in enumerate(draft.claims)
                ],
            )

    planner = Planner()
    runtime = Runtime(
        intake=Intake(),
        planner=planner,
        executor=PlanExecutor({"qualified_leaders": ToolCapability("qualified_leaders")}),
        synthesizer=WarehouseSynthesizer(),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=Semantic(),
    )
    result = await runtime.run("real assists leader lookup")
    assert planner.calls == 0
    assert result.verified_claims != []
    assert all(item.status == "complete" for item in result.output_statuses)


@pytest.mark.anyio
async def test_real_warehouse_second_single_fact_answers_through_fast_path(monkeypatch, tmp_path) -> None:
    import duckdb

    from shared import store
    from v2.adapters.core import ToolCapability

    warehouse = tmp_path / "fast_ratings.duckdb"
    connection = duckdb.connect(str(warehouse))
    connection.execute(
        "CREATE TABLE silver_team_ratings (TEAM_ID INTEGER, TEAM_NAME VARCHAR, "
        "GP INTEGER, W INTEGER, L INTEGER, OFF_RATING DOUBLE, DEF_RATING DOUBLE, "
        "NET_RATING DOUBLE, PACE DOUBLE, TS_PCT DOUBLE, TM_TOV_PCT DOUBLE, "
        "OFF_RATING_RANK INTEGER, DEF_RATING_RANK INTEGER, NET_RATING_RANK INTEGER, "
        "TS_PCT_RANK INTEGER, TM_TOV_PCT_RANK INTEGER, _season VARCHAR, "
        "_source VARCHAR, _fetched_at VARCHAR)"
    )
    connection.execute(
        "INSERT INTO silver_team_ratings VALUES (1, 'Capital City Stars', 82, 58, 24, "
        "119.8, 110.2, 9.6, 99.1, 0.601, 12.4, 1, 4, 1, 2, 6, '2025-26', 'fixture', "
        "'2026-04-14T00:00:00Z')"
    )
    connection.execute(
        "INSERT INTO silver_team_ratings VALUES (2, 'Rio Grande Rays', 82, 52, 30, "
        "117.3, 111.5, 5.8, 98.4, 0.589, 13.1, 3, 8, 3, 5, 11, '2025-26', 'fixture', "
        "'2026-04-14T00:00:00Z')"
    )
    connection.close()
    monkeypatch.setattr(store, "DB_PATH", warehouse)
    store.warehouse_identity_cache_clear()

    task = TaskSpec(
        goal="real ratings lookup",
        mode=RunMode.QUICK,
        deliverable="offensive rating",
        requested_outputs=[],
        season=SeasonRef(value="2025-26", source="user", confidence=1.0),
        requirements=[EvidenceRequirement(
            id="ratings_board",
            description="2025-26 offensive ratings",
            capability_options=["team_ratings"],
            capability_arguments={"requested_metric": "OFF_RATING", "ranking_direction": "desc"},
            requested_outputs=["OFF_RATING"],
        )],
    )

    class WarehouseSynthesizer:
        async def synthesize(self, task, evidence):
            envelope = list(evidence)[0] if isinstance(evidence, dict) else evidence[0]
            top = envelope.rows[0] if isinstance(envelope.rows, list) else envelope.rows
            value = float(top["OFF_RATING"])
            text = f"Capital City Stars posted {value} points per 100 possessions."
            claim = Claim(
                text=text,
                kind=ClaimKind.OBSERVED,
                evidence_ids=[envelope.evidence_id],
                output_bindings=[EvidenceOutputBinding(
                    requirement_kind="evidence",
                    requirement_id="ratings_board",
                    output_id="OFF_RATING",
                    node_id="fast",
                    evidence_id=envelope.evidence_id,
                    selector="rows[0].OFF_RATING",
                    value={"kind": "float", "value": value},
                    unit={"kind": "declared", "value": "points_per_100_possessions"},
                    domain="team_ratings",
                )],
            )
            return DraftReport(sections=["Answer"], claims=[claim])

    class Intake:
        async def understand(self, request: str, context=()) -> TaskSpec:
            return task

    class Planner:
        def __init__(self) -> None:
            self.calls = 0

        async def plan(self, task: TaskSpec, failure_context=None) -> Plan:
            self.calls += 1
            return Plan(nodes=[PlanNode(
                id="slow",
                description="slow ratings fetch",
                capability_hints=["team_ratings"],
                covers_requirement_ids=["ratings_board"],
                arguments={"requested_metric": "OFF_RATING", "ranking_direction": "desc"},
            )])

    class Semantic:
        async def verify(self, task, draft, evidence) -> VerificationReport:
            return VerificationReport(
                status=VerificationStatus.PASS,
                claim_results=[
                    {"claim_index": index, "supported": True}
                    for index, _claim in enumerate(draft.claims)
                ],
            )

    planner = Planner()
    runtime = Runtime(
        intake=Intake(),
        planner=planner,
        executor=PlanExecutor({"team_ratings": ToolCapability("team_ratings")}),
        synthesizer=WarehouseSynthesizer(),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=Semantic(),
    )
    result = await runtime.run("real ratings lookup")
    assert planner.calls == 0
    assert result.verified_claims != []
    assert all(item.status == "complete" for item in result.output_statuses)
