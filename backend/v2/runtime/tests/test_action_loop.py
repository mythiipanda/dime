from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from v2.adapters.models import RecordedStructuredModel
from v2.contracts import (
    CalculationOutputBinding, Claim, DeclaredCalculation,
    DeclaredCalculationInput, DraftReport, EntityRef, EvidenceEnvelope,
    EvidenceOutputBinding, EvidenceRequirement, SeasonRef, TaskSpec,
    VerificationReport, VerificationStatus,
)
from v2.runtime import FakeCapability, PlanExecutor
from v2.runtime.action_loop import ActionLoop, LoopAction
from v2.runtime.assembly import MechanicalVerifier, capability_catalog
from v2.runtime.checkpoints import FileCheckpointStore
from v2.runtime.ledger import LedgerKind, RunLedger
from v2.runtime.recording import RecordedCapability

class ScriptedModel:
    def __init__(self, actions, *, cancel: bool = False):
        self.actions = list(actions)
        self.cancel = cancel
        self.calls = []

    async def generate(self, *, schema, prompt, payload, envelope, decode=None):
        self.calls.append({"schema": schema, "payload": payload, "envelope": envelope})
        if self.cancel:
            raise asyncio.CancelledError()
        value = self.actions.pop(0)
        return schema.model_validate(
            value if "step" in value else {"step": value})

class PassSemantic:
    def __init__(self):
        self.calls = 0

    async def verify(self, task, draft, evidence):
        self.calls += 1
        return VerificationReport(
            status=VerificationStatus.PASS,
            claim_results=[
                {"claim_index": index, "supported": True}
                for index, _ in enumerate(draft.claims)])

@pytest.fixture
def anyio_backend():
    return "asyncio"

def task() -> TaskSpec:
    return TaskSpec(
        goal="wins", mode="quick", deliverable="wins",
        requested_outputs=["WINS"],
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[EntityRef(id="1610612738", type="team",
                            display_name="Boston Celtics")],
        requirements=[EvidenceRequirement(
            id="wins", description="wins",
            capability_options=["standings"])])

def tool_action(node_id="facts"):
    return {"action": "tool", "plan": {"nodes": [{
        "id": node_id, "description": "standings",
        "capability_hints": ["standings"], "covers_requirement_ids": ["wins"],
        "arguments": {"season": "2024-25"},
    }]}}

def binding(selector="rows[0].WINS", evidence_id="evidence:facts",
            node_id="facts", domain="standings"):
    return EvidenceOutputBinding(
        requirement_kind="task", requirement_id=None, output_id="WINS",
        node_id=node_id, evidence_id=evidence_id,
        selector=selector, row_selector="rows[0]",
        value={"kind": "integer", "value": 61},
        subject_entity_type="team", subject_entity_id="1610612738",
        subject_selector="rows[0].TEAM_ID",
        unit={"kind": "declared", "value": "count"}, domain=domain)

def answer(bindings=None, evidence_ids=None):
    return {"action": "answer", "draft": DraftReport(
        sections=["Record"], claims=[Claim(
            text="Boston Celtics won 61 games.", kind="observed",
            evidence_ids=evidence_ids or ["evidence:facts"],
            output_bindings=bindings if bindings is not None else [binding()],
        )]).model_dump(mode="json")}

def run_loop(actions, *, capabilities=None, max_actions=4, cancel=False,
             checkpoint_store=None):
    ledger = RunLedger("action-loop-test")
    scripted = ScriptedModel(actions, cancel=cancel)
    model = RecordedStructuredModel(scripted, ledger, turn_id="action-loop-test")
    raw_caps = capabilities or {
        "standings": FakeCapability(
            "standings", [{"TEAM_ID": 1610612738,
                           "TEAM_NAME": "Boston Celtics",
                           "WINS": 61, "LOSSES": 21}])}
    caps = {
        name: RecordedCapability(cap, ledger, turn_id="action-loop-test")
        for name, cap in raw_caps.items()
    }
    catalog = capability_catalog()
    loop = ActionLoop(
        model=model, executor=PlanExecutor(
            caps, checkpoint_store=checkpoint_store),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=PassSemantic(), ledger=ledger,
        tool_catalog={name: catalog[name] for name in caps},
        turn_id="action-loop-test", max_actions=max_actions)
    return loop, scripted, ledger

@pytest.mark.anyio
async def test_tool_answer_publishes_through_full_publication():
    loop, scripted, ledger = run_loop([tool_action(), answer()])
    result = await loop.run(task())
    assert result.verification.status == VerificationStatus.PASS
    assert result.gaps == []
    assert len(result.verified_claims) == 1
    claim = result.verified_claims[0]
    assert claim.sources[0].evidence_id == "evidence:facts"
    assert claim.sources[0].source == "fake"
    assert claim.sources[0].capability == "standings"
    bound = claim.output_bindings[0]
    assert (bound.selector, bound.unit.value, bound.domain) == (
        "rows[0].WINS", "count", "standings")
    assert [(item.output_id, item.status) for item in result.output_statuses] == [
        ("WINS", "complete")]
    assert scripted.calls[1]["payload"]["tools"]["standings"]["description"]
    assert scripted.calls[1]["payload"]["admitted_evidence"][0]["evidence_id"] == (
        "evidence:facts")
    kinds = {item.kind.value for item in ledger.entries}
    assert {LedgerKind.MODEL_REQUEST.value, LedgerKind.ASSISTANT_ATTEMPT.value,
            LedgerKind.TOOL_CALL.value, LedgerKind.TOOL_RESULT.value,
            LedgerKind.TURN_START.value, LedgerKind.TURN_END.value} <= kinds

@pytest.mark.anyio
async def test_complete_dependency_plan_executes_both_tools_and_publishes(tmp_path):
    dependency_task = TaskSpec(
        goal="wins", mode="quick", deliverable="wins",
        requested_outputs=["WINS"],
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[EntityRef(id="1610612738", type="team",
                            display_name="Boston Celtics")],
        required_evidence=["entity_resolution", "team_season_summary"],
        requirements=[
            EvidenceRequirement(id="resolve_celtics", description="resolve team",
                                capability_options=["entity_resolution"]),
            EvidenceRequirement(id="celtics_regular_season_summary",
                                description="summary",
                                capability_options=["team_season_summary"]),
        ])
    plan = {"action": "tool", "plan": {"nodes": [
        {"id": "resolve_celtics", "description": "resolve team",
         "capability_hints": ["entity_resolution"],
         "covers_requirement_ids": ["resolve_celtics"],
         "arguments": {"query": "Boston Celtics"}},
        {"id": "celtics_regular_season_summary", "description": "summary",
         "depends_on": ["resolve_celtics"],
         "capability_hints": ["team_season_summary"],
         "covers_requirement_ids": ["celtics_regular_season_summary"],
         "arguments": {"season": "2024-25", "period_scope": "regular_season"}},
    ]}}
    summary_binding = binding(
        evidence_id="evidence:celtics_regular_season_summary",
        node_id="celtics_regular_season_summary",
        domain="team_season_summary")
    loop, _, ledger = run_loop(
        [plan, answer(bindings=[summary_binding],
                      evidence_ids=["evidence:celtics_regular_season_summary"])],
        capabilities={
            "entity_resolution": FakeCapability(
                "entity_resolution",
                [{"TEAM_ID": 1610612738, "TEAM_NAME": "Boston Celtics"}]),
            "team_season_summary": FakeCapability(
                "team_season_summary",
                [{"TEAM_ID": 1610612738, "TEAM_NAME": "Boston Celtics",
                  "GAMES": 82, "WINS": 61, "LOSSES": 21,
                  "TOTAL_POINTS": 9795}]),
        }, max_actions=2, checkpoint_store=FileCheckpointStore(tmp_path))
    result = await loop.run(dependency_task)
    assert result.verification.status == VerificationStatus.PASS
    assert result.gaps == []
    assert len(result.verified_claims) == 1
    assert [(item.output_id, item.status) for item in result.output_statuses] == [
        ("WINS", "complete")]
    tool_calls = [item for item in ledger.entries
                  if item.kind == LedgerKind.TOOL_CALL]
    assert sorted(item.step_id for item in tool_calls) == [
        "celtics_regular_season_summary", "resolve_celtics"]
    assert {item.step_id for item in ledger.entries
            if item.kind == LedgerKind.TOOL_RESULT} == {
                "celtics_regular_season_summary", "resolve_celtics"}

@pytest.mark.anyio
async def test_incomplete_plan_is_rejected_without_tool_execution():
    dependency_task = TaskSpec(
        goal="wins", mode="quick", deliverable="wins",
        requested_outputs=["WINS"],
        required_evidence=["entity_resolution", "team_season_summary"],
        requirements=[
            EvidenceRequirement(id="resolve_celtics", description="resolve team",
                                capability_options=["entity_resolution"]),
            EvidenceRequirement(id="celtics_regular_season_summary",
                                description="summary",
                                capability_options=["team_season_summary"]),
        ])
    plan = {"action": "tool", "plan": {"nodes": [{
        "id": "celtics_regular_season_summary", "description": "summary",
        "capability_hints": ["team_season_summary"],
        "covers_requirement_ids": ["celtics_regular_season_summary"],
        "arguments": {"season": "2024-25"},
    }]}}
    loop, _, ledger = run_loop(
        [plan], capabilities={
            "entity_resolution": FakeCapability("entity_resolution", []),
            "team_season_summary": FakeCapability("team_season_summary", []),
        }, max_actions=1)
    result = await loop.run(dependency_task)
    assert result.verified_claims == []
    assert any("plan does not cover required evidence" in gap.message
               for gap in result.gaps)
    assert not any(item.kind in {LedgerKind.TOOL_CALL, LedgerKind.TOOL_RESULT}
                   for item in ledger.entries)

@pytest.mark.anyio
async def test_unknown_evidence_is_withheld():
    loop, _, _ = run_loop(
        [tool_action(), answer(bindings=[], evidence_ids=["missing"])],
        max_actions=2)
    result = await loop.run(task())
    assert result.verification.status == VerificationStatus.PARTIAL
    assert result.verified_claims == []
    assert any("unknown evidence" in gap.message for gap in result.gaps)

@pytest.mark.anyio
async def test_invalid_selector_is_not_published_as_complete():
    loop, _, _ = run_loop(
        [tool_action(), answer(bindings=[binding(selector="rows[0].MISSING")])],
        max_actions=2)
    result = await loop.run(task())
    assert all(item.status != "complete" for item in result.output_statuses)
    assert any("selector" in gap.message or "binding" in gap.message
               for gap in result.gaps)

@pytest.mark.anyio
async def test_typed_tool_defect_returns_to_same_loop():
    loop, scripted, _ = run_loop([
        {"action": "tool", "plan": {"nodes": [{
            "id": "bad", "description": "bad",
            "capability_hints": ["missing"],
            "covers_requirement_ids": ["wins"], "arguments": {},
        }]}},
        tool_action(), answer(),
    ], max_actions=3)
    result = await loop.run(task())
    assert result.gaps == []
    assert scripted.calls[1]["payload"]["defects"]
    assert len(result.verified_claims) == 1

@pytest.mark.anyio
async def test_captured_league_aggregate_is_withheld_by_admission():
    sql = ("SELECT AVG(TS_PCT) AS MEAN_TS_PCT, COUNT(*) AS PLAYER_COUNT "
           "FROM silver_player_season WHERE _season = '2024-25'")
    task_spec = TaskSpec(
        goal="league mean true shooting", mode="quick",
        deliverable="mean TS% and player count",
        requested_outputs=["MEAN_TS_PCT", "PLAYER_COUNT"],
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[EntityRef(id="league", type="league", display_name="NBA")],
        required_evidence=["sql_exec"],
        requirements=[EvidenceRequirement(
            id="mean_ts_pct_2024_25",
            description="mean TS% and player count",
            capability_options=["sql_exec"],
            capability_arguments={"season": "2024-25", "sql": sql})])
    evidence_id = "evidence:mean_ts_pct_2024_25_sql-replan2"
    draft = DraftReport(
        sections=["Result"], claims=[Claim(
            text=("Across the 2024-25 season, the league-wide mean true shooting "
                  "percentage is 0.545548330404218 over 569 player-season rows."),
            kind="observed", evidence_ids=[evidence_id],
            output_bindings=[
                EvidenceOutputBinding(
                    requirement_kind="task", requirement_id=None,
                    output_id="MEAN_TS_PCT", node_id="mean_ts_pct_2024_25",
                    evidence_id=evidence_id, selector="rows[0].MEAN_TS_PCT",
                    row_selector="rows[0]",
                    value={"kind": "float", "value": 0.545548330404218},
                    subject_entity_type="league", subject_entity_id="league",
                    subject_selector="rows[0]", unit={"kind": "unitless"},
                    domain="sql_exec"),
                EvidenceOutputBinding(
                    requirement_kind="task", requirement_id=None,
                    output_id="PLAYER_COUNT", node_id="mean_ts_pct_2024_25",
                    evidence_id=evidence_id, selector="rows[0].PLAYER_COUNT",
                    row_selector="rows[0]", value={"kind": "integer", "value": 569},
                    subject_entity_type="league", subject_entity_id="league",
                    subject_selector="rows[0]", unit={"kind": "unitless"},
                    domain="sql_exec"),
            ])])
    actions = [
        {"action": "tool", "plan": {"nodes": [{
            "id": "mean_ts_pct_2024_25_sql-replan2",
            "description": "SQL aggregate",
            "capability_hints": ["sql_exec"],
            "covers_requirement_ids": ["mean_ts_pct_2024_25"],
            "arguments": {"season": "2024-25", "sql": sql},
        }]}},
        {"action": "answer", "draft": draft.model_dump(mode="json")},
    ]
    loop, _, _ = run_loop(
        actions,
        capabilities={"sql_exec": FakeCapability(
            "sql_exec", [{"MEAN_TS_PCT": 0.545548330404218,
                          "PLAYER_COUNT": 569}])},
        max_actions=2)
    result = await loop.run(task_spec)
    assert result.verification.status == VerificationStatus.PARTIAL
    assert all(item.status != "complete" for item in result.output_statuses)
    assert any("identity authority" in gap.message for gap in result.gaps)
    assert all(not claim.output_bindings for claim in result.verified_claims)

@pytest.mark.anyio
async def test_action_budget_exhausts_to_partial_publication():
    loop, scripted, _ = run_loop(
        [tool_action("facts1"), tool_action("facts2")], max_actions=2)
    result = await loop.run(task())
    assert result.draft.claims == []
    assert result.verification.status == VerificationStatus.PARTIAL
    assert result.verified_claims == []
    assert any("action budget exhausted" in gap.message for gap in result.gaps)
    assert len(scripted.calls) == 2

@pytest.mark.anyio
async def test_invalid_answer_contract_returns_to_same_loop_then_publishes_supported_outputs():
    outputs = ["GAMES", "WINS", "LOSSES", "PTS", "TOTAL_POINTS", "PPG",
               "POINTS_PER_GAME", "MEAN_PPG"]
    evidence_id = "evidence:celtics_regular_season_summary"
    node_id = "celtics_regular_season_summary"
    requirement_id = "celtics_regular_season_summary"
    summary_task = TaskSpec(
        goal="Boston Celtics 2024-25 regular-season summary",
        mode="quick", deliverable="games, record, points, and points per game",
        requested_outputs=outputs,
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[EntityRef(id="1610612738", type="team",
                            display_name="Boston Celtics")],
        required_evidence=["entity_resolution", "team_season_summary"],
        requirements=[
            EvidenceRequirement(id="resolve_celtics", description="resolve team",
                                capability_options=["entity_resolution"]),
            EvidenceRequirement(
                id=requirement_id, description="available rows summary",
                capability_options=["team_season_summary"],
                requested_outputs=outputs),
        ])
    plan = {"action": "tool", "plan": {"nodes": [
        {"id": "resolve_celtics", "description": "resolve team",
         "capability_hints": ["entity_resolution"],
         "covers_requirement_ids": ["resolve_celtics"],
         "arguments": {"query": "Boston Celtics"}},
        {"id": node_id, "description": "available rows summary",
         "depends_on": ["resolve_celtics"],
         "capability_hints": ["team_season_summary"],
         "covers_requirement_ids": [requirement_id],
         "arguments": {"season": "2024-25", "period_scope": "regular_season"}},
    ]}}

    class CapturedSummary:
        name = "team_season_summary"
        task_season_scoped = True

        async def execute(self, node, task, evidence):
            return EvidenceEnvelope(
                evidence_id=evidence_id,
                capability="team_season_summary",
                source="v1:get_team_season_summary:warehouse:silver_hist_gamelogs",
                observed_at=datetime.now(UTC),
                season="2024-25",
                task_season_scoped=True,
                entities=[EntityRef(id="1610612738", type="team",
                                    display_name="1610612738")],
                rows=[{"TEAM_ID": 1610612738, "SEASON": "2024-25",
                       "PERIOD_SCOPE": "regular_season", "GAMES": 82,
                       "WINS": 61, "LOSSES": 21, "PTS": 9534,
                       "PPG": 116.26829268292683}],
                units={"GAMES": "count", "WINS": "count", "LOSSES": "count",
                       "PTS": "points", "PPG": "per_game"},
                coverage=("Summary of rows available for this team, season, "
                          "and regular-season source; season completeness is "
                          "unverified."),
                lineage=[item.evidence_id for item in evidence],
                warnings=["Values describe available warehouse rows only."])

    def observed(output_id, selector, kind, value, unit):
        return EvidenceOutputBinding(
            requirement_kind="evidence", requirement_id=requirement_id,
            output_id=output_id, node_id=node_id, evidence_id=evidence_id,
            selector=selector, row_selector="rows[0]",
            value={"kind": kind, "value": value},
            subject_entity_type="team", subject_entity_id="1610612738",
            subject_selector="rows[0].TEAM_ID",
            unit={"kind": "declared", "value": unit},
            domain="team_season_summary")

    def captured_invalid_answer():
        return {"action": "answer", "draft": DraftReport(
            sections=["Answer"], claims=[
                Claim(
                    text="Boston Celtics played 82 games in 2024-25.",
                    kind="observed", evidence_ids=[evidence_id],
                    output_bindings=[EvidenceOutputBinding(
                        requirement_kind="evidence",
                        requirement_id=requirement_id, output_id="GAMES",
                        node_id=node_id, evidence_id=evidence_id,
                        selector="$.rows[0].GAMES",
                        row_selector="$.rows[0]",
                        value={"kind": "integer", "value": 82},
                        subject_entity_type="team",
                        subject_entity_id="1610612738",
                        subject_selector="$.rows[0]",
                        unit={"kind": "declared", "value": "count"},
                        domain="team_season_summary")]),
                Claim(
                    text=("Mean points per game = 9534 / 82 = "
                          "116.26829268292683."),
                    kind="derived", evidence_ids=[evidence_id],
                    calculation_id="mean_ppg_fixture",
                    output_bindings=[CalculationOutputBinding(
                        requirement_id=requirement_id,
                        output_id="MEAN_PPG",
                        calculation_id="mean_ppg_fixture")]),
            ], calculations=[DeclaredCalculation(
                calculation_id="mean_ppg_fixture",
                requirement_id=requirement_id, operation="divide",
                inputs=[
                    DeclaredCalculationInput(
                        evidence_id=evidence_id, path="$.rows[0].PTS"),
                    DeclaredCalculationInput(
                        evidence_id=evidence_id, path="$.rows[0].GAMES"),
                ], result="116.26829268292683", unit="per_game")],
        ).model_dump(mode="json")}

    def unauthorized_calculation_answer():
        return {"action": "answer", "draft": DraftReport(
            sections=["Answer"], claims=[
                Claim(
                    text="Boston Celtics played 82 games in 2024-25.",
                    kind="observed", evidence_ids=[evidence_id],
                    output_bindings=[observed(
                        "GAMES", "rows[0].GAMES", "integer", 82, "count")]),
                Claim(
                    text=("Mean points per game = 9534 / 82 = "
                          "116.26829268292683."),
                    kind="derived", evidence_ids=[evidence_id],
                    calculation_id="mean_ppg_fixture",
                    output_bindings=[CalculationOutputBinding(
                        requirement_id=requirement_id,
                        output_id="MEAN_PPG",
                        calculation_id="mean_ppg_fixture")]),
            ], calculations=[DeclaredCalculation(
                calculation_id="mean_ppg_fixture",
                requirement_id=requirement_id, operation="divide",
                inputs=[
                    DeclaredCalculationInput(
                        evidence_id=evidence_id, path="rows[0].PTS"),
                    DeclaredCalculationInput(
                        evidence_id=evidence_id, path="rows[0].GAMES"),
                ], result="116.26829268292683", unit="per_game")],
        ).model_dump(mode="json")}

    def canonical_answer():
        return {"action": "answer", "draft": DraftReport(
            sections=["Answer"], claims=[
                Claim(
                    text=("Boston Celtics 2024-25 regular season: 82 games, "
                          "61 wins, 21 losses, 9,534 points, and "
                          "116.26829268292683 points per game."),
                    kind="observed", evidence_ids=[evidence_id],
                    output_bindings=[
                        observed("GAMES", "rows[0].GAMES", "integer", 82, "count"),
                        observed("WINS", "rows[0].WINS", "integer", 61, "count"),
                        observed("LOSSES", "rows[0].LOSSES", "integer", 21, "count"),
                        observed("PTS", "rows[0].PTS", "integer", 9534, "points"),
                        observed("TOTAL_POINTS", "rows[0].PTS", "integer", 9534,
                                 "points"),
                        observed("PPG", "rows[0].PPG", "float",
                                 116.26829268292683, "per_game"),
                        observed("POINTS_PER_GAME", "rows[0].PPG", "float",
                                 116.26829268292683, "per_game"),
                        observed("MEAN_PPG", "rows[0].PPG", "float",
                                 116.26829268292683, "per_game"),
                    ]),
            ]).model_dump(mode="json")}

    loop, scripted, _ = run_loop(
        [plan, captured_invalid_answer(), unauthorized_calculation_answer(),
         canonical_answer()],
        capabilities={
            "entity_resolution": FakeCapability("entity_resolution", [
                {"TEAM_ID": 1610612738, "TEAM_NAME": "Boston Celtics"}]),
            "team_season_summary": CapturedSummary(),
        }, max_actions=4)
    result = await loop.run(summary_task)

    assert len(scripted.calls) == 4
    assert [item["status"] for item in
            scripted.calls[3]["payload"]["actions"]] == [
        "complete", "rejected", "rejected"]
    first_defects = " ".join(
        item["message"] for item in scripted.calls[2]["payload"]["defects"])
    assert "$.rows[0].PTS" in first_defects
    assert "subject selector" in first_defects
    assert "calculation output is outside requirement" in first_defects
    second_defects = " ".join(
        item["message"] for item in scripted.calls[3]["payload"]["defects"])
    assert "binding calculation output is outside requirement" in second_defects
    summary = next(
        item for item in scripted.calls[1]["payload"]["admitted_evidence"]
        if item["capability"] == "team_season_summary")
    assert "season completeness is unverified" in summary["coverage"]
    assert summary["warnings"] == [
        "Values describe available warehouse rows only."]

    assert result.verification.status == VerificationStatus.PASS
    assert result.gaps == []
    assert result.draft.calculations == []
    assert len(result.verified_claims) == 1
    assert result.verified_claims[0].sources[0].source == (
        "v1:get_team_season_summary:warehouse:silver_hist_gamelogs")
    complete = {
        (item.requirement_kind, item.requirement_id, item.output_id)
        for item in result.output_statuses if item.status == "complete"}
    for output in outputs:
        assert ("task", None, output) in complete
        assert ("evidence", requirement_id, output) in complete
    assert all(item.requirement_kind != "calculation"
               for item in result.output_statuses)

@pytest.mark.anyio
async def test_cancellation_closes_ledger_and_propagates():
    loop, _, ledger = run_loop([], cancel=True, max_actions=2)
    with pytest.raises(asyncio.CancelledError):
        await loop.run(task())
    assert any(item.kind.value == LedgerKind.TURN_END.value
               and item.data.get("reason") == "cancelled"
               for item in ledger.entries)

def test_action_union_rejects_mixed_shapes():
    with pytest.raises(ValidationError):
        LoopAction.model_validate({"step": {
            "action": "tool", "capability": "standings",
            "node_id": "facts", "draft": {}}})
    with pytest.raises(ValidationError):
        LoopAction.model_validate({"step": {
            "action": "answer", "capability": "standings",
            "draft": {}}})
