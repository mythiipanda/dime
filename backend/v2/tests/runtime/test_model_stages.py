from datetime import UTC, datetime

import pytest

from app.config import settings

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
                    "capability_hints": ["standings"],}]},
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

    stub = StubModel([{"status": "pass", "claim_results": [
        {"claim_index": 0, "supported": True}]}])
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


def test_pydanticai_provider_boundary_preserves_ordered_fallback(monkeypatch) -> None:
    from v2.adapters.models import ProviderStructuredModel

    monkeypatch.setattr("v2.adapters.models.settings.inception_api_key", "primary")
    monkeypatch.setattr("v2.adapters.models.settings.mistral_api_key", "fallback")
    monkeypatch.setattr("v2.adapters.models.settings.openrouter_api_key", "")
    monkeypatch.setattr("v2.adapters.models.settings.groq_api_key", "")
    models = ProviderStructuredModel("inception", "mercury-test")._models()
    assert [provider for provider, _ in models] == ["inception", "mistral"]
    assert models[0][1].model_name == "mercury-test"
    assert models[1][1].model_name == settings.mistral_model


def test_pydanticai_models_keep_timeout_and_openrouter_attribution(monkeypatch) -> None:
    from v2.adapters.models import ProviderStructuredModel

    monkeypatch.setattr("v2.adapters.models.settings.openrouter_api_key", "key")
    monkeypatch.setattr("v2.adapters.models.settings.mistral_api_key", "")
    monkeypatch.setattr("v2.adapters.models.settings.inception_api_key", "")
    monkeypatch.setattr("v2.adapters.models.settings.groq_api_key", "")
    [(provider, model)] = ProviderStructuredModel(
        "openrouter", "openrouter/free")._models()
    assert provider == "openrouter"
    client = model.client
    assert client.timeout == settings.llm_timeout_s
    assert client.max_retries == 0
    assert client.default_headers["X-Title"] == "Dime NBA Analyst"


@pytest.mark.anyio
async def test_recorded_model_logs_actual_fallback_provenance() -> None:
    from v2.contracts import TaskSpec
    from v2.runtime import LedgerKind, RequestEnvelope, RunLedger
    from v2.adapters import RecordedStructuredModel

    class FallbackModel:
        last_provider = "mistral"
        last_model = "ministral-test"
        async def generate(self, **call):
            return TaskSpec(goal="answer", mode="quick", deliverable="text")

    envelope = RequestEnvelope.freeze(
        provider="inception", model="mercury-test", route="intake",
        prompt="prompt", context={}, tool_schemas={}, planner_version="v2")
    ledger = RunLedger("run")
    recorded = RecordedStructuredModel(FallbackModel(), ledger, turn_id="turn")
    await recorded.generate(
        schema=TaskSpec, prompt="prompt", payload={}, envelope=envelope)
    attempt = next(entry for entry in ledger.entries
                   if entry.kind == LedgerKind.ASSISTANT_ATTEMPT)
    assert attempt.data["provider"] == "mistral"
    assert attempt.data["model"] == "ministral-test"
    assert attempt.data["used_fallback"] is True


@pytest.mark.anyio
async def test_semantic_verifier_rejects_incomplete_claim_adjudication() -> None:
    from v2.contracts import Claim, DraftReport, TaskSpec

    stub = StubModel([{"status": "pass", "claim_results": []}])
    verifier = ModelSemanticVerifier(stub, provider="stub", model_name="stub-model")
    draft = DraftReport(sections=["Answer"], claims=[Claim(
        text="Boston won 61 games.", kind="observed", evidence_ids=["ev"])])
    with pytest.raises(ValueError, match="every claim exactly once"):
        await verifier.verify(
            TaskSpec(goal="record", mode="quick", deliverable="answer"),
            draft, {},
        )


@pytest.mark.anyio
async def test_semantic_verifier_rejects_contradictory_pass() -> None:
    from v2.contracts import Claim, DraftReport, TaskSpec

    stub = StubModel([{"status": "pass", "claim_results": [
        {"claim_index": 0, "supported": False, "reasons": ["unsupported"]}]}])
    verifier = ModelSemanticVerifier(stub, provider="stub", model_name="stub-model")
    draft = DraftReport(sections=["Answer"], claims=[Claim(
        text="Boston won 61 games.", kind="observed", evidence_ids=["ev"])])
    with pytest.raises(ValueError, match="pass contradicts"):
        await verifier.verify(
            TaskSpec(goal="record", mode="quick", deliverable="answer"),
            draft, {},
        )


@pytest.mark.anyio
async def test_synthesizer_rejects_unknown_evidence_ids() -> None:
    from v2.contracts import TaskSpec

    stub = StubModel([{
        "sections": ["Answer"],
        "claims": [{"text": "Boston won 61 games.", "kind": "observed",
                    "evidence_ids": ["invented"]}],
    }])
    synthesizer = ModelSynthesizer(stub, provider="stub", model_name="stub-model")
    with pytest.raises(ValueError, match="unknown evidence ids.*invented"):
        await synthesizer.synthesize(
            TaskSpec(goal="record", mode="quick", deliverable="answer"), [])


@pytest.mark.anyio
async def test_intake_rejects_unknown_required_capability() -> None:
    stub = StubModel([{
        "goal": "record", "mode": "quick", "deliverable": "answer",
        "required_evidence": ["invented_tool"],
    }])
    intake = ModelIntake(stub, **stage_kwargs())
    with pytest.raises(ValueError, match="unknown capabilities.*invented_tool"):
        await intake.understand("record")


@pytest.mark.anyio
async def test_verifier_structured_output_rejects_unknown_fields() -> None:
    from v2.contracts import DraftReport, TaskSpec

    stub = StubModel([{
        "status": "pass", "claim_results": [], "confidence": 1.0,
    }])
    verifier = ModelSemanticVerifier(stub, provider="stub", model_name="stub-model")
    with pytest.raises(Exception, match="Extra inputs are not permitted"):
        await verifier.verify(
            TaskSpec(goal="empty", mode="quick", deliverable="answer"),
            DraftReport(sections=[], claims=[]), {},
        )
