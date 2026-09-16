from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

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
async def test_intake_prompt_reserves_open_questions_for_user_blockers():
    from v2.prompts import load_prompt

    prompt = load_prompt("intake")
    assert "only user-answerable ambiguities" in prompt
    assert "Missing evidence, uncertain causes, unspecified explanatory factors" in prompt
    assert 'Never ask the user to preselect causes for "what changed," "why," role, value, fit, or replaceability' in prompt


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
async def test_semantic_verifier_allows_omitted_claim_adjudication() -> None:
    from v2.contracts import Claim, DraftReport, TaskSpec

    stub = StubModel([{"status": "partial", "claim_results": []}])
    verifier = ModelSemanticVerifier(stub, provider="stub", model_name="stub-model")
    draft = DraftReport(sections=["Answer"], claims=[Claim(
        text="Boston won 61 games.", kind="observed", evidence_ids=["ev"])])
    report = await verifier.verify(
        TaskSpec(goal="record", mode="quick", deliverable="answer"),
        draft, {},
    )
    assert report.claim_results == []
    assert report.status == "partial"


@pytest.mark.anyio
async def test_semantic_verifier_rejects_contradictory_pass() -> None:
    from v2.contracts import Claim, DraftReport, TaskSpec

    stub = StubModel([{"status": "pass", "claim_results": [
        {"claim_index": 0, "supported": False, "reasons": ["unsupported"]}]}])
    verifier = ModelSemanticVerifier(stub, provider="stub", model_name="stub-model")
    draft = DraftReport(sections=["Answer"], claims=[Claim(
        text="Boston won 61 games.", kind="observed", evidence_ids=["ev"])])
    with pytest.raises(Exception, match="pass status contradicts"):
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


@pytest.mark.anyio
async def test_model_repair_cannot_retain_rejected_claim_unchanged() -> None:
    from v2.contracts import Claim, DraftReport, TaskSpec, VerificationReport

    rejected = Claim(
        text="Boston won 62 games.", kind="observed", evidence_ids=["ev"])
    stub = StubModel([{
        "sections": ["Record"], "claims": [rejected.model_dump(mode="json")],
    }])
    repairer = ModelRepairer(stub, provider="stub", model_name="stub-model")
    report = VerificationReport(
        status="repair", claim_results=[{
            "claim_index": 0, "supported": False,
            "reasons": ["uncited numeral 62"],
        }],
    )
    evidence = EvidenceEnvelope(
        evidence_id="ev", capability="standings", source="fixture",
        observed_at=datetime.now(UTC), rows={"team": "Boston", "wins": 61},
    )
    repaired = await repairer.repair(
        TaskSpec(goal="record", mode="quick", deliverable="answer"),
        DraftReport(sections=["Record"], claims=[rejected]),
        {"ev": evidence}, report,
    )
    assert repaired.claims == []


@pytest.mark.anyio
async def test_semantic_verifier_receives_all_evidence_qualifiers() -> None:
    from datetime import date
    from v2.contracts import Claim, DraftReport, EntityRef, TaskSpec

    stub = StubModel([{"status": "pass", "claim_results": [
        {"claim_index": 0, "supported": True},
    ]}])
    verifier = ModelSemanticVerifier(stub, provider="stub", model_name="stub-model")
    evidence = EvidenceEnvelope(
        evidence_id="ev", capability="standings", source="fixture",
        observed_at=datetime(2026, 9, 15, tzinfo=UTC), as_of=date(2026, 4, 15),
        entities=[EntityRef(id="BOS", type="team", display_name="Boston Celtics")],
        rows={"wins": 61}, units={"wins": "games"},
        metric_definitions={"wins": "regular-season wins"},
        warnings=["partial season"], lineage=["parent"],
    )
    await verifier.verify(
        TaskSpec(goal="record", mode="quick", deliverable="answer"),
        DraftReport(sections=["Answer"], claims=[Claim(
            text="Boston won 61 games.", kind="observed", evidence_ids=["ev"])]),
        {"ev": evidence},
    )
    compact = stub.calls[0]["payload"]["evidence"][0]
    assert compact["observed_at"] == "2026-09-15T00:00:00+00:00"
    assert compact["as_of"] == "2026-04-15"
    assert compact["entities"][0]["id"] == "BOS"
    assert compact["units"] == {"wins": "games"}
    assert compact["metric_definitions"] == {"wins": "regular-season wins"}
    assert compact["warnings"] == ["partial season"]
    assert compact["lineage"] == ["parent"]


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"provider": " ", "model_name": "model"}, "provider"),
        ({"provider": "inception", "model_name": " "}, "model_name"),
        ({"provider": "inception", "model_name": "model", "planner_version": " "},
         "planner_version"),
    ],
)
def test_model_stage_requires_request_identity(kwargs, error) -> None:
    from v2.adapters.models import ModelSynthesizer

    with pytest.raises(ValueError, match=error):
        ModelSynthesizer(StubModel({}), **kwargs)


def test_recorded_model_requires_turn_identity():
    from v2.adapters import RecordedStructuredModel
    from v2.runtime import RunLedger

    with pytest.raises(ValueError, match="turn id must be non-empty"):
        RecordedStructuredModel(StubModel([]), RunLedger("run"), turn_id=" ")


@pytest.mark.anyio
async def test_recorded_model_rejects_untyped_output_and_records_failure():
    from v2.adapters import RecordedStructuredModel
    from v2.contracts import TaskSpec
    from v2.runtime import RequestEnvelope, RunLedger

    class Untyped:
        async def generate(self, **call):
            return {"goal": "answer"}

    envelope = RequestEnvelope.freeze(
        provider="p", model="m", route="intake", prompt="prompt",
        context={}, tool_schemas={}, planner_version="v2",
    )
    ledger = RunLedger("run")
    recorded = RecordedStructuredModel(Untyped(), ledger, turn_id="turn")
    with pytest.raises(TypeError, match="TaskSpec"):
        await recorded.generate(
            schema=TaskSpec, prompt="prompt", payload={}, envelope=envelope,
        )
    assert ledger.entries[-1].data["status"] == "failed"


@pytest.mark.anyio
async def test_recorded_model_marks_same_provider_model_fallback() -> None:
    from v2.adapters import RecordedStructuredModel
    from v2.contracts import TaskSpec
    from v2.runtime import LedgerKind, RequestEnvelope, RunLedger

    class ModelFallback:
        last_provider = "inception"
        last_model = "mercury-backup"
        async def generate(self, **call):
            return TaskSpec(goal="answer", mode="quick", deliverable="text")

    envelope = RequestEnvelope.freeze(
        provider="inception", model="mercury-primary", route="intake",
        prompt="prompt", context={}, tool_schemas={}, planner_version="v2")
    ledger = RunLedger("run")
    await RecordedStructuredModel(ModelFallback(), ledger, turn_id="turn").generate(
        schema=TaskSpec, prompt="prompt", payload={}, envelope=envelope)
    attempt = next(entry for entry in ledger.entries
                   if entry.kind == LedgerKind.ASSISTANT_ATTEMPT)
    assert attempt.data["used_fallback"] is True


@pytest.mark.anyio
async def test_provider_model_clears_last_success_before_failed_generation(monkeypatch) -> None:
    from v2.adapters.models import ProviderStructuredModel
    from v2.contracts import TaskSpec
    from v2.runtime import RequestEnvelope

    class FailingAgent:
        def __init__(self, *args, **kwargs): pass
        async def run(self, prompt):
            raise RuntimeError("down")

    class StubModel:
        model_name = "mercury"

    model = ProviderStructuredModel("inception", "mercury")
    model.last_provider = "inception"
    model.last_model = "old-success"
    monkeypatch.setattr(model, "_models", lambda: [("inception", StubModel())])
    monkeypatch.setattr("v2.adapters.models.Agent", FailingAgent)
    envelope = RequestEnvelope.freeze(
        provider="inception", model="mercury", route="intake", prompt="p",
        context={}, tool_schemas={}, planner_version="v2")
    with pytest.raises(RuntimeError, match="all structured-output providers failed"):
        await model.generate(schema=TaskSpec, prompt="p", payload={}, envelope=envelope)
    assert model.last_provider is None
    assert model.last_model is None


@pytest.mark.anyio
async def test_recorded_model_revalidates_copied_structured_output():
    from v2.adapters import RecordedStructuredModel
    from v2.contracts import TaskSpec
    from v2.runtime import RequestEnvelope, RunLedger

    class Invalid:
        async def generate(self, **call):
            valid = TaskSpec(goal="answer", mode="quick", deliverable="text")
            return valid.model_copy(update={"goal": " "})

    envelope = RequestEnvelope.freeze(
        provider="p", model="m", route="intake", prompt="prompt",
        context={}, tool_schemas={}, planner_version="v2",
    )
    ledger = RunLedger("run")
    with pytest.raises(ValueError, match="goal and deliverable"):
        await RecordedStructuredModel(Invalid(), ledger, turn_id="turn").generate(
            schema=TaskSpec, prompt="prompt", payload={}, envelope=envelope,
        )
    assert ledger.entries[-1].data["status"] == "failed"


@pytest.mark.anyio
async def test_provider_boundary_does_not_expose_provider_error_text(monkeypatch):
    from v2.adapters.models import ProviderStructuredModel
    from v2.contracts import TaskSpec
    from v2.runtime import RequestEnvelope

    class FailingAgent:
        def __init__(self, *args, **kwargs): pass
        async def run(self, prompt):
            raise RuntimeError("secret upstream body")

    class StubModel:
        model_name = "mercury"

    model = ProviderStructuredModel("inception", "mercury")
    monkeypatch.setattr(model, "_models", lambda: [("inception", StubModel())])
    monkeypatch.setattr("v2.adapters.models.Agent", FailingAgent)
    envelope = RequestEnvelope.freeze(
        provider="inception", model="mercury", route="intake", prompt="p",
        context={}, tool_schemas={}, planner_version="v2")

    with pytest.raises(RuntimeError) as caught:
        await model.generate(
            schema=TaskSpec, prompt="p", payload={}, envelope=envelope)

    assert str(caught.value) == "all structured-output providers failed"
    assert "secret upstream body" not in str(caught.value)

@pytest.mark.anyio
async def test_planner_retries_one_failed_structured_generation() -> None:
    from v2.contracts import Plan, TaskSpec

    class Flaky:
        def __init__(self):
            self.calls = 0
        async def generate(self, **call):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("all structured-output providers failed")
            return Plan(nodes=[])

    model = Flaky()
    planner = ModelPlanner(
        model, provider="test", model_name="test", capability_catalog={})
    plan = await planner.plan(TaskSpec(
        goal="trade", mode="quick", deliverable="answer"))
    assert plan.nodes == []
    assert model.calls == 2

@pytest.mark.anyio
async def test_model_repair_preserves_previously_supported_claims() -> None:
    from v2.contracts import Claim, DraftReport, TaskSpec, VerificationReport

    supported = Claim(text="Boston finished 56-26.", kind="observed",
                      evidence_ids=["ev"])
    rejected = Claim(text="Boston won 99 games.", kind="observed",
                     evidence_ids=["ev"])
    stub = StubModel([{
        "sections": ["Record"],
        "claims": [{"text": "boston-celtics finished 56-26.",
                    "kind": "observed", "evidence_ids": ["ev"]}],
    }])
    repairer = ModelRepairer(stub, provider="stub", model_name="stub-model")
    report = VerificationReport(status="repair", claim_results=[
        {"claim_index": 0, "supported": True},
        {"claim_index": 1, "supported": False, "reasons": ["uncited 99"]},
    ])
    evidence = EvidenceEnvelope(
        evidence_id="ev", capability="standings", source="fixture",
        observed_at=datetime.now(UTC), rows={"team": "Boston", "wins": 56})
    repaired = await repairer.repair(
        TaskSpec(goal="record", mode="quick", deliverable="answer"),
        DraftReport(sections=["Record"], claims=[supported, rejected]),
        {"ev": evidence}, report)
    assert supported in repaired.claims
    assert rejected not in repaired.claims


@pytest.mark.anyio
async def test_tool_capability_binds_dependency_lineage() -> None:
    from v2.adapters import ToolCapability
    from v2.contracts import EvidenceEnvelope, PlanNode, TaskSpec

    class Args(BaseModel):
        a: str
        b: str
    class CompareTool:
        name = "get_compare"
        args_schema = Args
        async def ainvoke(self, arguments):
            return {"ok": True, "rows": {"a": arguments["a"], "b": arguments["b"]},
                    "meta": {"source": "fixture"}}

    parent = EvidenceEnvelope(
        evidence_id="parent", capability="entity_resolution", source="fixture",
        observed_at=datetime.now(UTC), rows={"player": "Jaylen Brown"})
    result = await ToolCapability(
        "player_comparison", tools={"get_compare": CompareTool()}).execute(
            PlanNode(id="compare", description="compare",
                     capability_hints=["player_comparison"],
                     arguments={"a": "Jaylen Brown", "b": "Paul George"}),
            TaskSpec(goal="compare", mode="quick", deliverable="answer"), [parent])
    assert result.lineage == ["parent"]

@pytest.mark.anyio
async def test_intake_drops_two_sided_evidence_for_one_player_question() -> None:
    from v2.contracts import EntityRef

    stub = StubModel([{
        "goal": "Assess trading Brown", "mode": "quick", "deliverable": "answer",
        "entities": [{"id": "1627759", "type": "player", "display_name": "Jaylen Brown"}],
        "required_evidence": ["player_evaluation", "trade_value", "player_comparison"],
    }])
    intake = ModelIntake(stub, provider="stub", model_name="stub-model",
        capability_catalog={"player_evaluation": {}, "trade_value": {},
                            "player_comparison": {}})
    task = await intake.understand("Should Boston trade Brown?")
    assert task.required_evidence == ["player_evaluation"]

@pytest.mark.anyio
async def test_intake_turns_tool_resolvable_team_question_into_assumption() -> None:
    stub = StubModel([{
        "goal": "Brown for Paul George", "mode": "quick", "deliverable": "answer",
        "entities": [
            {"id": "1627759", "type": "player", "display_name": "Jaylen Brown"},
            {"id": "202331", "type": "player", "display_name": "Paul George"},
        ],
        "required_evidence": ["entity_resolution", "contracts"],
        "open_questions": ["Which team is Paul George currently on?"],
    }])
    intake = ModelIntake(stub, provider="stub", model_name="stub-model",
        capability_catalog={"entity_resolution": {}, "contracts": {}})
    task = await intake.understand("What about Brown for Paul George?")
    assert task.open_questions == []
    assert task.assumptions == ["Which team is Paul George currently on?"]

@pytest.mark.anyio
async def test_intake_preserves_trade_value_for_two_player_trade() -> None:
    stub = StubModel([{
        "goal": "Brown for George", "mode": "quick", "deliverable": "answer",
        "entities": [
            {"id": "1627759", "type": "player", "display_name": "Jaylen Brown"},
            {"id": "202331", "type": "player", "display_name": "Paul George"},
        ],
        "required_evidence": ["player_evaluation", "trade_value", "player_comparison"],
    }])
    intake = ModelIntake(stub, provider="stub", model_name="stub-model",
        capability_catalog={"player_evaluation": {}, "trade_value": {},
                            "player_comparison": {}})
    task = await intake.understand("Brown for George?")
    assert task.required_evidence == [
        "player_evaluation", "trade_value", "player_comparison"]

@pytest.mark.anyio
async def test_intake_turns_contract_and_risk_questions_into_assumptions() -> None:
    questions = [
        "Specific remaining years and player options on contracts for both players",
        "Explicit risk tolerance of the Celtics front office for roster changes",
    ]
    stub = StubModel([{
        "goal": "Brown for George", "mode": "quick", "deliverable": "answer",
        "required_evidence": ["contracts", "player_evaluation"],
        "open_questions": questions,
    }])
    intake = ModelIntake(stub, provider="stub", model_name="stub-model",
        capability_catalog={"contracts": {}, "player_evaluation": {}})
    task = await intake.understand("Brown for George?")
    assert task.open_questions == []
    assert task.assumptions == questions

@pytest.mark.anyio
async def test_followup_trade_uses_context_performance_season_not_forward_default() -> None:
    from v2.contracts import ConversationTurn
    stub = StubModel([{
        "goal": "Brown for George", "mode": "quick", "deliverable": "answer",
        "season": {"value": "2026-27", "source": "default", "confidence": 0.9},
        "skills": ["trade-analysis"],
    }])
    intake = ModelIntake(stub, provider="stub", model_name="stub-model",
        capability_catalog={})
    task = await intake.understand("What about Brown for Paul George?", context=(
        ConversationTurn(role="user", content="Assess Brown in 2025-26."),
        ConversationTurn(role="assistant", content="Brown's 2025-26 role was large."),
    ))
    assert task.season.value == "2025-26"
    assert task.season.source == "context"

@pytest.mark.anyio
async def test_intake_removes_skills_from_required_evidence_and_trade_intent_blocker() -> None:
    stub = StubModel([{
        "goal": "Brown for George", "mode": "quick", "deliverable": "answer",
        "skills": ["trade-analysis", "player-comparison"],
        "required_evidence": ["trade-analysis", "player-comparison", "contracts"],
        "open_questions": ["Celtics front office current trade intent for Brown"],
    }])
    intake = ModelIntake(stub, provider="stub", model_name="stub-model",
        capability_catalog={"contracts": {}})
    task = await intake.understand("Brown for George?")
    assert task.required_evidence == ["contracts"]
    assert task.open_questions == []
    assert task.assumptions == ["Celtics front office current trade intent for Brown"]

@pytest.mark.anyio
async def test_semantic_verifier_retries_one_failed_structured_generation() -> None:
    from v2.contracts import Claim, DraftReport, TaskSpec, VerificationReport
    class Flaky:
        def __init__(self): self.calls = 0
        async def generate(self, **call):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("all structured-output providers failed")
            return VerificationReport(status="pass", claim_results=[
                {"claim_index": 0, "supported": True}])
    model = Flaky()
    verifier = ModelSemanticVerifier(model, provider="test", model_name="test")
    report = await verifier.verify(
        TaskSpec(goal="record", mode="quick", deliverable="answer"),
        DraftReport(sections=["Record"], claims=[Claim(
            text="Boston won.", kind="judgment")]), {})
    assert report.claim_results[0].supported
    assert model.calls == 2

@pytest.mark.anyio
async def test_trade_skill_requires_complete_two_player_evidence_baseline() -> None:
    from v2.contracts import TaskSpec

    stub = StubModel([{
        "goal": "Brown for George", "mode": "deep_dive",
        "deliverable": "trade analysis",
        "entities": [
            {"id": "1627759", "type": "player", "display_name": "Jaylen Brown"},
            {"id": "202331", "type": "player", "display_name": "Paul George"},
        ],
        "skills": ["trade-analysis"],
        "required_evidence": ["player_evaluation"],
    }])
    catalog = {name: {} for name in (
        "player_report", "player_evaluation", "player_comparison",
        "trade_value", "contracts", "trades",
    )}
    task = await ModelIntake(
        stub, provider="stub", model_name="stub", capability_catalog=catalog,
    ).understand("Would Brown for Paul George make sense?")
    assert task.required_evidence == [
        "player_evaluation", "player_report", "player_comparison",
        "trade_value", "contracts", "trades",
    ]


@pytest.mark.anyio
async def test_trade_skill_baseline_does_not_expand_one_player_question() -> None:
    stub = StubModel([{
        "goal": "Should Boston trade Brown", "mode": "deep_dive",
        "deliverable": "analysis",
        "entities": [
            {"id": "1627759", "type": "player", "display_name": "Jaylen Brown"},
        ],
        "skills": ["trade-analysis"],
        "required_evidence": ["player_evaluation", "trade_value"],
    }])
    catalog = {name: {} for name in (
        "player_report", "player_evaluation", "player_comparison",
        "trade_value", "contracts", "trades",
    )}
    task = await ModelIntake(
        stub, provider="stub", model_name="stub", capability_catalog=catalog,
    ).understand("Should Boston trade Brown?")
    assert task.required_evidence == ["player_evaluation"]

@pytest.mark.anyio
async def test_requirement_review_repairs_omitted_compound_branches():
    catalog = {
        "team_ratings": "team ratings", "player_ratings": "player ratings",
        "playoff_team_ratings": "playoff ratings", "playoffs": "results",
    }
    stub = StubModel([{
        "goal": "rank last season offense and defense", "mode": "deep_dive",
        "deliverable": "rankings", "season": {
            "value": "2025-26", "source": "user", "confidence": 1,
        }, "subquestions": ["playoff results"], "required_evidence": ["playoffs"],
    }, {
        "missing_subquestions": [
            "rank regular-season teams", "rank qualified players",
            "rank playoff teams by rating",
        ],
        "requirements": [
            {"id": "regular_team_ratings", "description": "rank regular-season teams", "capability_options": ["team_ratings"]},
            {"id": "player_ratings", "description": "rank qualified players", "capability_options": ["player_ratings"]},
            {"id": "playoff_team_ratings", "description": "rank playoff teams", "capability_options": ["playoff_team_ratings"]},
        ],
        "missing_skills": ["league-ratings"],
    }])
    task = await ModelIntake(
        stub, provider="stub", model_name="stub-model",
        capability_catalog=catalog, requirement_review=True,
    ).understand("Rank the best offensive and defensive teams and players, including playoffs")
    assert task.required_evidence == ["playoffs"]
    assert [item.id for item in task.requirements] == [
        "regular_team_ratings", "player_ratings", "playoff_team_ratings",
    ]
    assert task.subquestions == [
        "playoff results", "rank regular-season teams", "rank qualified players",
        "rank playoff teams by rating",
    ]
    assert task.skills == ["league-ratings"]
    assert stub.calls[1]["envelope"].route == "requirement_review"


@pytest.mark.anyio
async def test_planner_replans_when_first_plan_omits_required_evidence():
    from v2.contracts import Plan, TaskSpec

    stub = StubModel([
        {"nodes": [{"id": "results", "description": "results",
                    "capability_hints": ["playoffs"]}]},
        {"nodes": [
            {"id": "results", "description": "results",
             "capability_hints": ["playoffs"]},
            {"id": "ratings", "description": "ratings",
             "capability_hints": ["team_ratings"],
             "covers_requirement_ids": ["team_ratings"]},
        ]},
    ])
    planner = ModelPlanner(
        stub, provider="stub", model_name="stub-model",
        capability_catalog={"playoffs": {}, "team_ratings": {}},
    )
    plan = await planner.plan(TaskSpec(
        goal="ratings", mode="deep_dive", deliverable="ranking",
        required_evidence=["team_ratings"],
    ))
    assert {node.capability_hints[0] for node in plan.nodes} == {
        "playoffs", "team_ratings",
    }
    assert stub.calls[1]["payload"]["coverage_feedback"] == {
        "missing_required_evidence": ["team_ratings"],
        "instruction": "Return a complete replacement plan.",
    }
