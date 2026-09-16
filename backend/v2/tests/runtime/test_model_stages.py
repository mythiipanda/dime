from datetime import UTC, datetime

import pytest

from v2.adapters.models import (
    ModelIntake,
    ModelPlanner,
    ModelRepairer,
    ModelSemanticVerifier,
    ModelSynthesizer,
)
from v2.contracts import EvidenceEnvelope


class StubModel:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = []

    async def generate(self, **call):
        self.calls.append(call)
        return call["schema"].model_validate(next(self.values))


def stage_kwargs():
    return {"provider": "stub", "model_name": "stub-model",
            "capability_catalog": {"standings": "team standings"}}


@pytest.mark.anyio
async def test_model_backed_stages_form_a_structured_slice():
    stub = StubModel([
        {"goal": "Boston record", "mode": "quick", "deliverable": "text",
         "required_evidence": ["standings"]},
        {"nodes": [{"id": "facts", "description": "standings",
                    "capability_hints": ["standings"],
                    "completion_test": "one Boston row"}]},
        {"sections": ["Record"], "claims": [{"text": "Boston won 61 games.",
          "kind": "observed", "evidence_ids": ["ev"]}]},
        {"status": "pass", "claim_results": [
          {"claim_index": 0, "supported": True}]},
    ])
    intake = ModelIntake(stub, **stage_kwargs())
    planner = ModelPlanner(stub, **stage_kwargs())
    synthesizer = ModelSynthesizer(
        stub, provider="stub", model_name="stub-model")
    verifier = ModelSemanticVerifier(
        stub, provider="stub", model_name="stub-model")

    task = await intake.understand("What is Boston's record?")
    plan = await planner.plan(task)
    evidence = EvidenceEnvelope(
        evidence_id="ev", capability="standings", source="fixture",
        observed_at=datetime.now(UTC), rows={"team": "Boston", "wins": 61})
    draft = await synthesizer.synthesize(task, [evidence])
    report = await verifier.verify(task, draft, {"ev": evidence})

    assert plan.nodes[0].capability_hints == ["standings"]
    assert draft.claims[0].evidence_ids == ["ev"]
    assert report.status == "pass"
    assert all(call["envelope"].provider == "stub" for call in stub.calls)
    assert len({call["envelope"].route for call in stub.calls}) == 4



@pytest.mark.anyio
async def test_recorded_model_keeps_success_and_failure_attempts():
    from v2.adapters import RecordedStructuredModel
    from v2.contracts import TaskSpec
    from v2.runtime import LedgerKind, RequestEnvelope, RunLedger

    class Failing:
        async def generate(self, **call):
            raise RuntimeError("provider down")

    envelope = RequestEnvelope.freeze(provider="p", model="m", route="intake",
        prompt="prompt", context={}, tool_schemas={}, planner_version="v2")
    ledger = RunLedger("run")
    recorded = RecordedStructuredModel(Failing(), ledger, turn_id="turn")
    with pytest.raises(RuntimeError, match="provider down"):
        await recorded.generate(schema=TaskSpec, prompt="prompt", payload={}, envelope=envelope)

    assert [entry.kind for entry in ledger.entries] == [
        LedgerKind.MODEL_REQUEST, LedgerKind.ASSISTANT_ATTEMPT]
    assert ledger.entries[-1].data["status"] == "failed"


@pytest.mark.anyio
async def test_model_repair_receives_only_typed_admitted_context():
    from v2.contracts import Claim, DraftReport, TaskSpec, VerificationReport

    stub = StubModel([{
        "sections": ["Record"],
        "claims": [{"text": "Boston won 61 games.", "kind": "observed",
                    "evidence_ids": ["ev"]}],
        "gaps": ["salary evidence is 2026-27, not 2025-26"],
    }])
    repairer = ModelRepairer(stub, provider="stub", model_name="stub-model")
    task = TaskSpec(goal="record", mode="quick", deliverable="text")
    draft = DraftReport(sections=["Record"], claims=[
        Claim(text="Boston won 62 games.", kind="observed", evidence_ids=["ev"])])
    report = VerificationReport(status="repair", repair_instructions=[
        "Repair claim 0: uncited numeral 62"])
    evidence = EvidenceEnvelope(
        evidence_id="ev", capability="standings", source="fixture",
        observed_at=datetime.now(UTC), rows={"team": "Boston", "wins": 61})

    repaired = await repairer.repair(task, draft, {"ev": evidence}, report)
    payload = stub.calls[0]["payload"]
    assert set(payload) == {"task", "draft", "verification", "admitted_evidence", "skills"}
    assert payload["skills"] == []
    assert payload["admitted_evidence"][0]["evidence_id"] == "ev"
    assert repaired.claims[0].text == "Boston won 61 games."

@pytest.mark.anyio
async def test_intake_receives_bounded_followup_context_without_full_skill_bodies():
    from v2.contracts import ConversationTurn

    stub = StubModel([{
        "goal": "assess Jaylen Brown trade value on Boston",
        "mode": "deep_dive", "deliverable": "analysis",
        "skills": ["trade-analysis"],
    }])
    intake = ModelIntake(stub, **stage_kwargs())
    context = [
        ConversationTurn(role="user", content=f"turn {index}")
        for index in range(10)
    ]
    task = await intake.understand(
        "Now assess his value on that team", context=context)
    payload = stub.calls[0]["payload"]
    assert [turn["content"] for turn in payload["conversation_context"]] == [
        f"turn {index}" for index in range(2, 10)
    ]
    assert task.skills == ["trade-analysis"]
    assert all("instructions" not in item for item in payload["skill_catalog"])


@pytest.mark.anyio
async def test_semantic_verifier_receives_vintage_and_source_scope() -> None:
    from v2.adapters.models import ModelSemanticVerifier
    from v2.contracts import Claim, DraftReport, EvidenceEnvelope, TaskSpec

    stub = StubModel([{"status": "pass", "claim_results": []}])
    verifier = ModelSemanticVerifier(stub, provider="stub", model_name="stub-model")
    task = TaskSpec(goal="trade", mode="deep_dive", deliverable="analysis")
    draft = DraftReport(sections=["Trade"], claims=[Claim(
        text="Brown's salary is $57.1M.", kind="observed", evidence_ids=["ev"])])
    evidence = EvidenceEnvelope(
        evidence_id="ev", capability="trade_value", source="v1:get_trade_value:salary",
        observed_at=datetime.now(UTC), vintages={"salary_season": "2026-27"},
        task_season_scoped=False, rows={"salary": 57_100_000})
    await verifier.verify(task, draft, {"ev": evidence})
    compact = stub.calls[0]["payload"]["evidence"][0]
    assert compact["source"] == "v1:get_trade_value:salary"
    assert compact["vintages"] == {"salary_season": "2026-27"}
    assert compact["task_season_scoped"] is False


@pytest.mark.anyio
async def test_intake_receives_explicit_current_date() -> None:
    stub = StubModel([{"goal": "record", "mode": "quick", "deliverable": "answer"}])
    intake = ModelIntake(stub, **stage_kwargs())
    await intake.understand("current record")
    current_date = stub.calls[0]["payload"]["current_date"]
    assert len(current_date) == 10
    assert current_date.count("-") == 2
