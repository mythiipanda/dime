from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from v2.adapters.models import RecordedStructuredModel
from v2.contracts import (
    Claim, DraftReport, EntityRef, EvidenceOutputBinding, EvidenceRequirement,
    SeasonRef, TaskSpec, VerificationReport, VerificationStatus,
)
from v2.runtime import FakeCapability, PlanExecutor
from v2.runtime.action_loop import ActionLoop, LoopAction
from v2.runtime.assembly import MechanicalVerifier, capability_catalog
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
        return schema.model_validate(self.actions.pop(0))

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
    return {"action": "tool", "capability": "standings", "node_id": node_id,
            "arguments": {"season": "2024-25"}}

def binding(selector="rows[0].WINS"):
    return EvidenceOutputBinding(
        requirement_kind="task", requirement_id=None, output_id="WINS",
        node_id="facts", evidence_id="evidence:facts",
        selector=selector, row_selector="rows[0]",
        value={"kind": "integer", "value": 61},
        subject_entity_type="team", subject_entity_id="1610612738",
        subject_selector="rows[0].TEAM_ID",
        unit={"kind": "declared", "value": "count"}, domain="standings")

def answer(bindings=None, evidence_ids=None):
    return {"action": "answer", "draft": DraftReport(
        sections=["Record"], claims=[Claim(
            text="Boston Celtics won 61 games.", kind="observed",
            evidence_ids=evidence_ids or ["evidence:facts"],
            output_bindings=bindings if bindings is not None else [binding()],
        )]).model_dump(mode="json")}

def run_loop(actions, *, capabilities=None, max_actions=4, cancel=False):
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
        model=model, executor=PlanExecutor(caps),
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
        {"action": "tool", "capability": "missing", "node_id": "bad",
         "arguments": {}},
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
        {"action": "tool", "capability": "sql_exec",
         "node_id": "mean_ts_pct_2024_25_sql-replan2",
         "arguments": {"season": "2024-25", "sql": sql}},
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
async def test_cancellation_closes_ledger_and_propagates():
    loop, _, ledger = run_loop([], cancel=True, max_actions=2)
    with pytest.raises(asyncio.CancelledError):
        await loop.run(task())
    assert any(item.kind.value == LedgerKind.TURN_END.value
               and item.data.get("reason") == "cancelled"
               for item in ledger.entries)

def test_action_union_rejects_mixed_shapes():
    with pytest.raises(ValidationError):
        LoopAction.model_validate({"action": "tool", "capability": "standings",
                                   "node_id": "facts", "draft": {}})
    with pytest.raises(ValidationError):
        LoopAction.model_validate({"action": "answer", "capability": "standings",
                                   "draft": {}})
