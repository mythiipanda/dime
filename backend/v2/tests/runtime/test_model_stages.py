from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from app.config import settings

from v2.adapters.models import (
    PlannerArgumentError,
    ModelIntake,
    ModelPlanner,
    ModelRepairer,
    ModelSemanticVerifier,
    ModelSynthesizer,
    capability_arguments_for,
    provider_to_source,
)
from v2.contracts import EvidenceEnvelope, TaskSpec, PlanNode, RequirementReview
from v2.arguments import PlannerOutputWire, RequirementReviewWire, SLOTS


class StubModel:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = []

    @staticmethod
    def _wire_entry(key, value):
        if value is None: kind,slot='null','value'
        elif type(value) is bool: kind,slot='bool','bool_value'
        elif type(value) is int: kind,slot='int','int_value'
        elif type(value) is float: kind,slot='number','number_value'
        elif type(value) is str: kind,slot='string','string_value'
        elif type(value) is list and (not value or all(type(x) is str for x in value)): kind,slot='string_list','string_list_value'
        else: raise ValueError(f'fixture cannot encode {key}')
        slots={name:None for name in SLOTS.values()};slots[slot]=value
        return {'key':key,'kind':kind,**slots}
    @classmethod
    def _migrate_fixture(cls, schema, value):
        if schema is PlannerOutputWire:
            for n in value.get('nodes',[]):
                if len(n.get('capability_hints') or []) > 1:
                    raise ValueError(f"fixture node {n['id']!r} has several capability_hints; the wire takes one capability")
            return {'nodes':[{'id':n['id'],'description':n['description'],'depends_on':n.get('depends_on'),
             'capability':(n.get('capability_hints') or [n.get('capability')])[0],
             'covers_requirement_ids':n.get('covers_requirement_ids'),'arguments':{'entries':[cls._wire_entry(k,v) for k,v in n.get('arguments',{}).items()]},
             'max_attempts':n.get('max_attempts'),'status':n.get('status')} for n in value.get('nodes',[])]}
        if schema is RequirementReviewWire:
            rows=[]
            for r in value.get('requirements',[]):
                options=r['capability_options'];shared=r.get('capability_arguments',{})
                sets=r.get('capability_argument_sets') or [{'capability_id':c,'arguments':shared} for c in options]
                rows.append({'id':r['id'],'description':r['description'],'capability_options':options,
                 'capability_argument_sets':[{'capability_id':x['capability_id'],'arguments':{'entries':[cls._wire_entry(k,v) for k,v in x.get('arguments',{}).items()]}} for x in sets],
                 'metric_ids':r.get('metric_ids'),'requested_outputs':r.get('requested_outputs')})
            return {'requirements':rows,'calculation_requirements':value.get('calculation_requirements'),
             'missing_subquestions':value.get('missing_subquestions'),'missing_skills':value.get('missing_skills')}
        return value
    async def generate(self, **call):
        self.calls.append(call);value=next(self.values)
        return call["schema"].model_validate(self._migrate_fixture(call['schema'],value))


def fixture_result(call, value):
    raw=value.model_dump(mode="json") if isinstance(value,BaseModel) else value
    return call["schema"].model_validate(StubModel._migrate_fixture(call["schema"],raw))

def stage_kwargs():
    return {"provider": "stub", "model_name": "stub-model",
            "capability_catalog": {"standings": {}}}


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
async def test_followup_intake_resolves_context_reference_before_user_blocker():
    from v2.contracts import ConversationTurn

    stub = StubModel([
        {
            "goal": "Explain that success and whether he can sustain it",
            "mode": "deep_dive", "deliverable": "analysis",
            "entities": [
                {"id": "1610612760", "type": "team",
                 "display_name": "Oklahoma City Thunder"},
            ],
            "open_questions": ["Who does he refer to?"],
        },
        {
            "goal": "Explain Oklahoma City's success and whether Shai can sustain it",
            "mode": "deep_dive", "deliverable": "analysis",
            "entities": [
                {"id": "1610612760", "type": "team",
                 "display_name": "Oklahoma City Thunder"},
                {"id": "1628983", "type": "player",
                 "display_name": "Shai Gilgeous-Alexander"},
            ],
        },
    ])
    intake = ModelIntake(stub, **stage_kwargs())
    task = await intake.understand(
        "What drove that success, and can he sustain it?", context=(
            ConversationTurn(role="user", content="Assess Oklahoma City."),
            ConversationTurn(
                role="assistant",
                content="Oklahoma City led the league behind Shai Gilgeous-Alexander."),
        ))

    assert task.open_questions == []
    assert [entity.display_name for entity in task.entities] == [
        "Oklahoma City Thunder", "Shai Gilgeous-Alexander",
    ]
    assert len(stub.calls) == 2
    feedback = stub.calls[1]["payload"]["resolution_feedback"]
    assert feedback["unresolved_questions"] == ["Who does he refer to?"]
    assert stub.calls[1]["payload"]["prior_intake"]["open_questions"] == [
        "Who does he refer to?",
    ]


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


def test_pydanticai_provider_boundary_uses_only_active_free_rotation(monkeypatch) -> None:
    from v2.adapters.models import ProviderStructuredModel

    # Inception stays configured for a future key rotation, but configured is
    # not active: Dime's own model stages may only select free providers.
    monkeypatch.setattr("v2.adapters.models.settings.nvidia_nim_api_key", "nim-key")
    monkeypatch.setattr("v2.adapters.models.settings.inception_api_key", "configured-paused")
    monkeypatch.setattr("v2.adapters.models.settings.mistral_api_key", "free-limit")
    monkeypatch.setattr("v2.adapters.models.settings.openrouter_api_key", "free-key")
    monkeypatch.setattr("v2.adapters.models.settings.groq_api_key", "configured-paused")
    models = ProviderStructuredModel("inception", "mercury-test")._models()
    assert [provider for provider, _ in models] == ["nvidia", "openrouter", "mistral"]
    assert models[0][1].model_name == settings.nvidia_nim_model
    assert models[1][1].model_name.endswith(":free")
    assert models[2][1].model_name == settings.mistral_model


def test_pydanticai_models_keep_timeout_and_openrouter_attribution(monkeypatch) -> None:
    from v2.adapters.models import ProviderStructuredModel

    monkeypatch.setattr("v2.adapters.models.settings.nvidia_nim_api_key", "")
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
    stub = StubModel([
        {"sections": ["Record"], "claims": [rejected.model_dump(mode="json")]},
        {"sections": [], "claims": []},
    ])
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
    assert repaired.gaps == [
        "A rejected evidence branch could not be corrected from the available data."]
    assert stub.calls[1]["payload"]["required_replacements"] == [{
        "claim_index": 0, "kind": "observed", "evidence_ids": ["ev"],
        "calculation_id": None,
    }]


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

    assert str(caught.value) == (
        "all structured-output providers failed "
        "[inception:RuntimeError:provider_error, inception:RuntimeError:provider_error]"
    )
    assert "secret upstream body" not in str(caught.value)

@pytest.mark.anyio
async def test_planner_does_not_outer_retry_failed_structured_generation() -> None:
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
    with pytest.raises(RuntimeError, match="all structured-output providers failed"):
        await planner.plan(TaskSpec(goal="trade", mode="quick", deliverable="answer"))
    assert model.calls == 1

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
    from v2.contracts import EvidenceEnvelope, TaskSpec, PlanNode

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
async def test_semantic_verifier_does_not_outer_retry_failed_generation() -> None:
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
    with pytest.raises(RuntimeError, match="all structured-output providers failed"):
        await verifier.verify(
            TaskSpec(goal="record", mode="quick", deliverable="answer"),
            DraftReport(sections=["Record"], claims=[Claim(
                text="Boston won.", kind="judgment")]), {})
    assert model.calls == 1

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
    catalog = {name:{} for name in ("team_ratings","player_ratings","playoff_team_ratings","playoffs")}
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
    assert task.required_evidence == [
        "playoffs", "team_ratings", "player_ratings", "playoff_team_ratings",
    ]
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


@pytest.mark.anyio
async def test_matchup_winner_requirement_selects_prediction_capability():
    stub = StubModel([{
        "goal": "predict Celtics vs Knicks", "mode": "quick",
        "deliverable": "winner", "entities": [
            {"id": "1610612738", "type": "team", "display_name": "Boston Celtics"},
            {"id": "1610612752", "type": "team", "display_name": "New York Knicks"},
        ], "required_evidence": [],
    }, {
        "requirements": [{
            "id": "winner", "description": "predict the matchup winner",
            "capability_options": ["game_prediction"],
        }],
        "missing_subquestions": [], "missing_skills": [],
    }])
    task = await ModelIntake(stub, provider="stub", model_name="stub",
        capability_catalog={"game_prediction": {}}, requirement_review=True
    ).understand("Who wins Celtics vs Knicks?")
    assert task.requirements[0].capability_options == ["game_prediction"]


@pytest.mark.anyio
async def test_planner_drops_false_requirement_coverage_from_supplemental_node():
    task = TaskSpec(
        goal="compare teams", mode="deep_dive", deliverable="analysis",
        requirements=[{
            "id": "health", "description": "rotation health",
            "capability_options": ["roster"],
        }],
    )
    stub = StubModel([{"nodes": [
        {
            "id": "roster", "description": "roster context",
            "capability_hints": ["roster"],
            "covers_requirement_ids": ["health"],
        },
        {
            "id": "news", "description": "supplemental discovery",
            "capability_hints": ["web_search"],
            "covers_requirement_ids": ["health"],
            "arguments": {"query": "current injuries"},
        },
    ]}])
    plan = await ModelPlanner(
        stub, provider="stub", model_name="stub",
        capability_catalog={"roster": {}, "web_search": {}},
    ).plan(task)
    assert plan.nodes[0].covers_requirement_ids == ["health"]
    assert plan.nodes[1].covers_requirement_ids == []


@pytest.mark.anyio
async def test_external_discovery_requirement_accepts_fetched_evidence():
    stub = StubModel([
        {
            "goal": "check current status", "mode": "quick",
            "deliverable": "status", "required_evidence": ["web_search"],
        },
        {
            "requirements": [{
                "id": "current_status", "description": "current status",
                "capability_options": ["web_search"],
            }],
            "missing_subquestions": [], "missing_skills": [],
        },
    ])
    task = await ModelIntake(
        stub, provider="stub", model_name="stub",
        capability_catalog={"web_search": {}, "web_fetch": {}},
        requirement_review=True,
    ).understand("What is the current status?")
    assert task.requirements[0].capability_options == ["web_search"]  # BL-001 fail-closed exact sets


@pytest.mark.anyio
async def test_model_repair_keeps_corrected_rejected_branch():
    from v2.contracts import (
        Claim, DraftReport, EvidenceEnvelope, TaskSpec, VerificationReport,
    )
    stub = StubModel([{
        "sections": ["Offense"],
        "claims": [{
            "text": "San Antonio ranked third at 118.7 points per 100 possessions.",
            "kind": "observed", "evidence_ids": ["ratings"],
        }],
        "gaps": ["Houston was incorrectly third and should be replaced."],
    }])
    repairer = ModelRepairer(stub, provider="stub", model_name="stub")
    evidence = EvidenceEnvelope(evidence_id="ratings", capability="team_ratings",
        source="warehouse", observed_at=datetime.now(UTC), season="2025-26",
        rows=[{"RANK": 3, "TEAM": "San Antonio", "OFF_RATING": 118.7}],
        qualification="All teams", coverage="Full league")
    draft = DraftReport(sections=["Offense"], claims=[Claim(
        text="Houston ranked third at 118.7 points per 100 possessions.",
        kind="observed", evidence_ids=["ratings"])])
    verification = VerificationReport(status="repair", claim_results=[{
        "claim_index": 0, "supported": False, "reasons": ["entity rank mismatch"]}],
        repair_instructions=["Repair claim 0 using the cited ranking row."])
    repaired = await repairer.repair(
        TaskSpec(goal="rank offense", mode="quick", deliverable="answer"),
        draft, {"ratings": evidence}, verification,
    )
    assert [claim.text for claim in repaired.claims] == [
        "San Antonio ranked third at 118.7 points per 100 possessions."]
    assert repaired.gaps == []


@pytest.mark.anyio
async def test_model_repair_requires_distinct_replacements_for_shared_evidence():
    from v2.contracts import Claim, DraftReport, TaskSpec, VerificationReport

    claims = [
        Claim(text="Boston was first.", kind="observed", evidence_ids=["ratings"]),
        Claim(text="Houston was third.", kind="observed", evidence_ids=["ratings"]),
    ]
    stub = StubModel([
        {"sections": ["Ratings"], "claims": [{
            "text": "Boston was first.", "kind": "observed",
            "evidence_ids": ["ratings"],
        }]},
        {"sections": ["Ratings"], "claims": [
            {"text": "Boston was first.", "kind": "observed",
             "evidence_ids": ["ratings"]},
            {"text": "San Antonio was third.", "kind": "observed",
             "evidence_ids": ["ratings"]},
        ]},
    ])
    repairer = ModelRepairer(stub, provider="stub", model_name="stub")
    evidence = EvidenceEnvelope(
        evidence_id="ratings", capability="team_ratings", source="warehouse",
        observed_at=datetime.now(UTC), rows=[
            {"rank": 1, "team": "Boston"}, {"rank": 3, "team": "San Antonio"}],
    )
    verification = VerificationReport(status="repair", claim_results=[
        {"claim_index": 0, "supported": True},
        {"claim_index": 1, "supported": False, "reasons": ["rank mismatch"]},
    ])
    repaired = await repairer.repair(
        TaskSpec(goal="rank teams", mode="quick", deliverable="answer"),
        DraftReport(sections=["Ratings"], claims=claims), {"ratings": evidence},
        verification,
    )
    assert stub.calls[1]["payload"]["required_replacements"][0]["claim_index"] == 1
    assert [claim.text for claim in repaired.claims] == [
        "Boston was first.", "San Antonio was third."]


@pytest.mark.anyio
async def test_matchup_optional_date_does_not_block_general_prediction():
    stub = StubModel([{
        "goal": "predict Celtics vs Knicks", "mode": "quick",
        "deliverable": "winner", "required_evidence": ["game_prediction"],
        "open_questions": [
            "What is the specific date of the game you are interested in?"
        ],
    }])
    task = await ModelIntake(
        stub, provider="stub", model_name="stub",
        capability_catalog={"game_prediction": {}},
    ).understand("Who wins Celtics vs Knicks?")
    assert task.open_questions == []
    assert task.assumptions == [
        "What is the specific date of the game you are interested in?"
    ]


@pytest.mark.anyio
async def test_two_team_winner_request_requires_prediction_even_if_intake_chooses_ratings():
    stub = StubModel([{
        "goal": "predict Celtics vs Knicks", "mode": "quick",
        "deliverable": "winner", "entities": [
            {"id": "bos", "type": "team", "display_name": "Boston Celtics"},
            {"id": "nyk", "type": "team", "display_name": "New York Knicks"},
        ], "required_evidence": ["team_ratings"], "skills": ["league-ratings"],
    }])
    task = await ModelIntake(
        stub, provider="stub", model_name="stub",
        capability_catalog={"team_ratings": {}, "game_prediction": {}},
    ).understand("Who wins Celtics vs Knicks?")
    assert task.required_evidence == ["team_ratings", "game_prediction"]
    assert task.season is None


@pytest.mark.anyio
async def test_implicit_matchup_season_is_pinned_to_prediction_data_vintage():
    from app.tools._core import SEASON
    stub = StubModel([{
        "goal": "predict Celtics vs Knicks", "mode": "quick",
        "deliverable": "winner", "entities": [
            {"id": "bos", "type": "team", "display_name": "Boston Celtics"},
            {"id": "nyk", "type": "team", "display_name": "New York Knicks"},
        ], "season": {"value": "2026-27", "source": "default", "confidence": 0.9},
        "required_evidence": ["game_prediction"],
    }])
    task = await ModelIntake(
        stub, provider="stub", model_name="stub",
        capability_catalog={"game_prediction": {}},
    ).understand("Who wins Celtics vs Knicks?")
    assert task.season.value == SEASON
    assert task.season.source == "default"


@pytest.mark.anyio
async def test_league_ratings_skill_requires_rating_populations_not_scoring_leaders():
    stub = StubModel([{
        "goal": "rank offense and defense", "mode": "deep_dive",
        "deliverable": "team player and playoff rankings",
        "skills": ["league-ratings"],
        "required_evidence": ["qualified_leaders"],
    }])
    catalog = {name: {} for name in (
        "qualified_leaders", "team_ratings", "player_ratings",
        "playoff_team_ratings",
    )}
    task = await ModelIntake(
        stub, provider="stub", model_name="stub", capability_catalog=catalog,
    ).understand("best offensive and defensive teams and players plus playoff ratings")
    assert task.required_evidence == [
        "qualified_leaders", "team_ratings", "player_ratings",
        "playoff_team_ratings",
    ]

@pytest.mark.anyio
async def test_planner_rejects_wrong_metric_argument_as_false_coverage():
    from v2.contracts import TaskSpec

    task = TaskSpec(
        goal="compare a percentage across seasons", mode="deep_dive",
        deliverable="ranked change",
        requirements=[{
            "id": "later_percentage", "description": "later qualified percentage",
            "capability_options": ["qualified_leaders"],
            "capability_arguments": {
                "stat_category": "FG3_PCT", "season": "2025-26",
                "ranking_direction": "desc", "min_attempts": 100,
            },
        }],
    )
    stub = StubModel([
        {"nodes": [{
            "id": "wrong_stat", "description": "later leaders",
            "capability_hints": ["qualified_leaders"],
            "covers_requirement_ids": ["later_percentage"],
            "arguments": {
                "stat_category": "PTS", "season": "2025-26",
                "ranking_direction": "desc", "min_attempts": 100,
            },
        }]},
        {"nodes": [{
            "id": "right_stat", "description": "later percentage leaders",
            "capability_hints": ["qualified_leaders"],
            "covers_requirement_ids": ["later_percentage"],
            "arguments": {
                "stat_category": "FG3_PCT", "season": "2025-26",
                "ranking_direction": "desc", "min_attempts": 100,
            },
        }]},
    ])
    plan = await ModelPlanner(
        stub, provider="stub", model_name="stub",
        capability_catalog={"qualified_leaders": {}},
    ).plan(task)
    assert plan.nodes[0].arguments == {
        "stat_category": "FG3_PCT", "season": "2025-26",
        "ranking_direction": "desc", "min_attempts": 100,
    }
    assert plan.nodes[0].covers_requirement_ids == ["later_percentage"]
    assert stub.calls[1]["payload"]["coverage_feedback"] == {
        "missing_requirement_ids": ["later_percentage"],
        "instruction": "Return a complete replacement plan.",
    }


def test_requirement_argument_matching_is_generic_and_nested():
    from v2.adapters.models import ModelPlanner

    assert ModelPlanner._arguments_cover(
        {"season": ["2024-25", "2025-26"], "filters": {"qualified": True}},
        {"season": "2025-26", "filters": {"qualified": True, "limit": 10}},
    )
    assert not ModelPlanner._arguments_cover(
        {"season": "2024-25", "stat_category": "FG3_PCT"},
        {"season": "2025-26", "stat_category": "PTS"},
    )

@pytest.mark.anyio
async def test_playoff_translation_skill_does_not_force_unrequested_capabilities():
    stub = StubModel([{
        "goal": "compare one player's regular season with his playoffs",
        "mode": "quick", "deliverable": "comparison",
        "skills": ["playoff-translation"],
        "required_evidence": ["player_report", "game_logs"],
    }])
    catalog = {name: {} for name in (
        "player_report", "game_logs", "team_ratings", "playoff_team_ratings",
        "clutch", "injuries", "roster",
    )}
    task = await ModelIntake(
        stub, provider="stub", model_name="stub", capability_catalog=catalog,
    ).understand("Compare his regular season with his playoffs")
    assert task.required_evidence == ["player_report", "game_logs"]

@pytest.mark.anyio
async def test_synthesizer_retries_one_failed_structured_generation() -> None:
    from v2.contracts import Claim, DraftReport, TaskSpec

    class Flaky:
        def __init__(self):
            self.calls = 0

        async def generate(self, **call):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("all structured-output providers failed")
            return DraftReport(sections=["Record"], claims=[Claim(
                text="Boston had the best record.", kind="judgment")])

    model = Flaky()
    draft = await ModelSynthesizer(
        model, provider="test", model_name="test",
    ).synthesize(
        TaskSpec(goal="best record", mode="quick", deliverable="answer"), [])

    assert draft.sections == ["Record"]
    assert model.calls == 2


@pytest.mark.anyio
async def test_synthesizer_does_not_retry_unrelated_runtime_error() -> None:
    class Broken:
        def __init__(self):
            self.calls = 0

        async def generate(self, **call):
            self.calls += 1
            raise RuntimeError("contract bug")

    model = Broken()
    with pytest.raises(RuntimeError, match="contract bug"):
        await ModelSynthesizer(
            model, provider="test", model_name="test",
        ).synthesize(
            TaskSpec(goal="record", mode="quick", deliverable="answer"), [])
    assert model.calls == 1


@pytest.mark.anyio
async def test_synthesizer_requires_every_independent_calculation_or_named_block():
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope, TaskSpec, PlanNode

    task = TaskSpec(
        goal="compare regular season and playoffs", mode="deep_dive",
        deliverable="three rating changes",
        calculation_requirements=[
            {"id": "off_change", "description": "playoff minus regular offense"},
            {"id": "def_change", "description": "playoff minus regular defense"},
            {"id": "net_change", "description": "playoff minus regular net"},
        ],
    )
    evidence = EvidenceEnvelope(
        evidence_id="ratings", capability="team_ratings", source="fixture",
        observed_at=datetime.now(UTC), rows={"off": 120.0, "playoff_off": 111.4},
    )
    stub = StubModel([{
        "sections": ["Changes"], "claims": [],
        "calculations": [{
            "calculation_id": "off", "requirement_id": "off_change",
            "operation": "subtract", "inputs": [
                {"evidence_id": "ratings", "path": "rows.playoff_off"},
                {"evidence_id": "ratings", "path": "rows.off"},
            ], "result": -8.6,
        }],
        "blocked_calculation_requirement_ids": [], "gaps": [],
    }])
    with pytest.raises(ValueError, match="def_change.*net_change"):
        await ModelSynthesizer(
            stub, provider="stub", model_name="stub",
        ).synthesize(task, [evidence])


@pytest.mark.anyio
async def test_synthesizer_accepts_declared_or_blocked_calculation_ledger():
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope, TaskSpec, PlanNode

    task = TaskSpec(
        goal="compare regular season and playoffs", mode="deep_dive",
        deliverable="three rating changes",
        calculation_requirements=[
            {"id": "off_change", "description": "offense change"},
            {"id": "def_change", "description": "defense change"},
            {"id": "net_change", "description": "net change"},
        ],
    )
    evidence = EvidenceEnvelope(
        evidence_id="ratings", capability="team_ratings", source="fixture",
        observed_at=datetime.now(UTC), rows={"off": 120.0, "playoff_off": 111.4},
    )
    stub = StubModel([{
        "sections": ["Changes"], "claims": [],
        "calculations": [{
            "calculation_id": "off", "requirement_id": "off_change",
            "operation": "subtract", "inputs": [
                {"evidence_id": "ratings", "path": "rows.playoff_off"},
                {"evidence_id": "ratings", "path": "rows.off"},
            ], "result": -8.6,
        }],
        "blocked_calculation_requirement_ids": ["def_change", "net_change"],
        "gaps": ["defense and net inputs missing"],
    }])
    draft = await ModelSynthesizer(
        stub, provider="stub", model_name="stub",
    ).synthesize(task, [evidence])
    assert draft.blocked_calculation_requirement_ids == ["def_change", "net_change"]

@pytest.mark.anyio
async def test_planner_dedupes_semantic_calls_and_keeps_other_branches():
    task = TaskSpec(
        goal="league assists leader", mode="quick", deliverable="answer",
        requirements=[{
            "id": "assists", "description": "assists leaderboard",
            "capability_options": ["team_totals"],
            "capability_arguments": {"stat": "AST"},
        }],
    )
    stub = StubModel([{"nodes": [
        {"id": "assists_a", "description": "assists",
         "capability_hints": ["team_totals"], "arguments": {"stat": "AST"},
         "covers_requirement_ids": ["assists"]},
        {"id": "assists_b", "description": "duplicate assists",
         "capability_hints": ["team_totals"], "arguments": {"stat": "AST"},
         "covers_requirement_ids": ["assists"]},
        {"id": "unasked_points", "description": "unasked points",
         "capability_hints": ["team_totals"], "arguments": {"stat": "PTS"}},
    ]}])
    plan = await ModelPlanner(
        stub, provider="stub", model_name="stub",
        capability_catalog={"team_totals": {}},
    ).plan(task)
    assert [node.id for node in plan.nodes] == ["assists_a", "unasked_points"]
    assert plan.nodes[0].covers_requirement_ids == ["assists"]


@pytest.mark.anyio
async def test_planner_keeps_same_call_when_parent_lineage_differs():
    task = TaskSpec(goal="compare", mode="quick", deliverable="answer")
    stub = StubModel([{"nodes": [
        {"id": "left", "description": "left", "capability_hints": ["resolve"],
         "arguments": {"query": "same"}},
        {"id": "right", "description": "right", "capability_hints": ["resolve"],
         "arguments": {"query": "other"}},
        {"id": "left_stats", "description": "stats", "depends_on": ["left"],
         "capability_hints": ["stats"], "arguments": {"season": "2025-26"}},
        {"id": "right_stats", "description": "stats", "depends_on": ["right"],
         "capability_hints": ["stats"], "arguments": {"season": "2025-26"}},
    ]}])
    plan = await ModelPlanner(
        stub, provider="stub", model_name="stub",
        capability_catalog={"resolve": {}, "stats": {}},
    ).plan(task)
    assert len(plan.nodes) == 4

@pytest.mark.anyio
async def test_intake_drops_capability_subsumed_required_evidence():
    stub = StubModel([{
        "goal": "Assess Curry's scoring efficiency", "mode": "quick",
        "deliverable": "answer", "entities": [{
            "id": "201939", "type": "player", "display_name": "Stephen Curry",
        }],
        "required_evidence": ["player_report", "shooting_efficiency"],
    }])
    task = await ModelIntake(
        stub, provider="stub", model_name="stub",
        capability_catalog={"player_report": {}, "shooting_efficiency": {}},
    ).understand("Assess Curry's scoring efficiency")
    assert task.required_evidence == ["player_report"]


@pytest.mark.anyio
async def test_planner_prunes_capability_subsumed_same_subject_call():
    task = TaskSpec(
        goal="Curry efficiency", mode="quick", deliverable="answer",
        requirements=[{
            "id": "efficiency", "description": "Curry shooting efficiency",
            "capability_options": ["player_report", "shooting_efficiency"],
        }],
    )
    stub = StubModel([{"nodes": [
        {"id": "report", "description": "full report",
         "capability_hints": ["player_report"],
         "arguments": {"player_id": 201939, "season": "2025-26"}},
        {"id": "efficiency", "description": "redundant efficiency",
         "capability_hints": ["shooting_efficiency"],
         "arguments": {"player_id": 201939, "season": "2025-26"},
         "covers_requirement_ids": ["efficiency"]},
    ]}])
    plan = await ModelPlanner(
        stub, provider="stub", model_name="stub",
        capability_catalog={"player_report": {}, "shooting_efficiency": {}},
    ).plan(task)
    assert [node.id for node in plan.nodes] == ["report"]
    assert plan.nodes[0].covers_requirement_ids == ["efficiency"]

@pytest.mark.anyio
async def test_synthesizer_cannot_reclassify_evidence_requirement_as_calculation_block():
    task = TaskSpec(
        goal="qualified three point leaders", mode="quick",
        deliverable="leaderboard",
        requirements=[{
            "id": "three_point_pct_leaders",
            "description": "qualified three point percentage leaders",
            "capability_options": ["qualified_leaders"],
        }],
    )
    stub = StubModel([{
        "sections": ["Leaders"], "claims": [],
        "blocked_calculation_requirement_ids": ["three_point_pct_leaders"],
        "gaps": [],
    }])
    draft = await ModelSynthesizer(
        stub, provider="stub", model_name="stub",
    ).synthesize(task, [])
    assert draft.blocked_calculation_requirement_ids == []


@pytest.mark.anyio
async def test_synthesizer_rejects_declared_calculation_for_evidence_requirement():
    task = TaskSpec(
        goal="qualified three point leaders", mode="quick",
        deliverable="leaderboard",
        requirements=[{
            "id": "three_point_pct_leaders",
            "description": "qualified three point percentage leaders",
            "capability_options": ["qualified_leaders"],
        }],
    )
    stub = StubModel([{
        "sections": ["Leaders"], "claims": [],
        "calculations": [{
            "calculation_id": "wrong_class",
            "requirement_id": "three_point_pct_leaders",
            "operation": "mean", "inputs": [{
                "evidence_id": "leaders", "path": "rows.value",
            }], "result": 0,
        }],
    }])
    draft = await ModelSynthesizer(
        stub, provider="stub", model_name="stub",
    ).synthesize(task, [])
    assert draft.claims == [] and draft.calculations == []
    assert "outside admitted evidence" in draft.gaps[0]
@pytest.mark.anyio
async def test_provider_structured_failure_preserves_sanitized_diagnostics(monkeypatch):
    from v2.adapters.models import ProviderStructuredModel
    from v2.runtime import RequestEnvelope

    class FailingAgent:
        def __init__(self, *args, **kwargs):
            pass
        async def run(self, prompt):
            assert "secret payload" in prompt
            raise TimeoutError("secret upstream body and bearer token")

    monkeypatch.setattr("v2.adapters.models.Agent", FailingAgent)
    model = ProviderStructuredModel("inception", "mercury-2.5")
    monkeypatch.setattr(model, "_models", lambda: [
        ("inception", type("M", (), {"model_name": "mercury-2.5"})()),
    ])
    envelope = RequestEnvelope.freeze(
        provider="inception", model="mercury-2.5", route="synthesizer",
        prompt="prompt", context={}, tool_schemas={}, planner_version="v2",
    )
    with pytest.raises(RuntimeError) as caught:
        await model.generate(
            schema=TaskSpec, prompt="prompt",
            payload={"evidence": "secret payload"}, envelope=envelope,
        )
    text = str(caught.value)
    assert "inception:TimeoutError:timeout" in text
    assert "secret payload" not in text
    assert "secret upstream" not in text
    assert len(model.last_failures) == 1
    assert {key: model.last_failures[0][key] for key in (
        "provider", "exception_type", "message_class")} == {
        "provider": "inception", "exception_type": "TimeoutError",
        "message_class": "timeout"}
    assert model.last_failures[0]["attempt_number"] == 1
    assert model.last_failures[0]["latency_ms"] >= 0
@pytest.mark.anyio
async def test_intake_season_normalization_propagates_to_requirement_arguments():
    from app.tools._core import SEASON

    stub = StubModel([
        {
            "goal": "current leaders", "mode": "quick", "deliverable": "answer",
            "season": {"value": "2026-27", "source": "default", "confidence": 0.9},
            "required_evidence": ["game_prediction"],
        },
        {
            "requirements": [{
                "id": "prediction", "description": "current prediction",
                "capability_options": ["game_prediction"],
                "capability_arguments": {"season": "2026-27"},
            }],
        },
    ])
    task = await ModelIntake(
        stub, provider="stub", model_name="stub",
        capability_catalog={"game_prediction": {}}, requirement_review=True,
    ).understand("current prediction")
    assert task.season.value == SEASON
    assert task.requirements[0].capability_arguments["season"] == SEASON
@pytest.mark.anyio
async def test_planner_replans_call_missing_catalog_required_arguments():
    task = TaskSpec(
        goal="current roster", mode="quick", deliverable="answer",
        required_evidence=["roster"],
        requirements=[{
            "id": "team_roster", "description": "team roster",
            "capability_options": ["roster"],
        }],
    )
    catalog = {"roster": {
        "description": "Team roster",
        "arguments": {
            "type": "object", "properties": {
                "team_id": {"type": "integer"},
                "season": {"type": "string"},
            }, "required": ["team_id"],
        },
    }}
    stub = StubModel([
        {"nodes": [{
            "id": "team_roster", "description": "roster",
            "capability_hints": ["roster"],
            "covers_requirement_ids": ["team_roster"],
            "arguments": {"season": "2025-26"},
        }]},
        {"nodes": [{
            "id": "team_roster", "description": "roster",
            "capability_hints": ["roster"],
            "covers_requirement_ids": ["team_roster"],
            "arguments": {"team_id": 1610612760, "season": "2025-26"},
        }]},
    ])
    plan = await ModelPlanner(
        stub, provider="stub", model_name="stub", capability_catalog=catalog,
    ).plan(task)
    assert plan.nodes[0].arguments["team_id"] == 1610612760
    assert len(stub.calls) == 2
    assert "coverage_feedback" not in stub.calls[0]["payload"]
    assert stub.calls[1]["payload"]["coverage_feedback"] == {
        "missing_required_arguments": {"team_roster": ["team_id"]},
        "instruction": "Return a complete replacement plan.",
    }


@pytest.mark.anyio
async def test_planner_fails_closed_when_replan_still_misses_required_argument():
    task = TaskSpec(
        goal="current roster", mode="quick", deliverable="answer",
        required_evidence=["roster"],
        requirements=[{
            "id": "team_roster", "description": "team roster",
            "capability_options": ["roster"],
        }],
    )
    catalog = {"roster": {
        "description": "Team roster",
        "arguments": {
            "type": "object", "properties": {
                "team_id": {"type": "integer"},
                "season": {"type": "string"},
            }, "required": ["team_id"],
        },
    }}
    missing = {"nodes": [{
        "id": "team_roster", "description": "roster",
        "capability_hints": ["roster"],
        "covers_requirement_ids": ["team_roster"],
        "arguments": {"season": "2025-26"},
    }]}
    stub = StubModel([missing, missing])
    with pytest.raises(PlannerArgumentError, match="'team_id' is a required property") as caught:
        await ModelPlanner(
            stub, provider="stub", model_name="stub", capability_catalog=catalog,
        ).plan(task)
    assert caught.value.missing_required == ["team_id"]
    assert len(stub.calls) == 2

@pytest.mark.anyio
async def test_requirement_review_retries_one_provider_exhaustion() -> None:
    class FlakyReview:
        def __init__(self):
            self.calls = 0
        async def generate(self, **call):
            self.calls += 1
            if self.calls == 1:
                return TaskSpec(goal="leaders", mode="quick", deliverable="answer")
            if self.calls == 2:
                raise RuntimeError("all structured-output providers failed [inception:ModelHTTPError:provider_error]")
            return call["schema"].model_validate({"requirements": []})

    model = FlakyReview()
    task = await ModelIntake(
        model, provider="stub", model_name="stub",
        capability_catalog={}, requirement_review=True,
    ).understand("leaders")

    assert task.goal == "leaders"
    assert model.calls == 2
@pytest.mark.anyio
async def test_requirement_review_closes_narrow_option_over_broader_capability():
    stub = StubModel([{
        "goal": "player line", "mode": "quick", "deliverable": "answer",
        "entities": [{"id": "luka", "type": "player", "display_name": "Luka"}],
        "required_evidence": ["player_report", "shooting_efficiency"],
    }, {
        "requirements": [{
            "id": "shooting", "description": "shooting splits",
            "capability_options": ["shooting_efficiency"],
            "capability_arguments": {"player": "luka", "season": "2022-23"},
        }],
    }])
    task = await ModelIntake(
        stub, provider="stub", model_name="stub", requirement_review=True,
        capability_catalog={"player_report": {}, "shooting_efficiency": {}},
    ).understand("Luka's 2022-23 line")
    assert task.requirements[0].capability_options == ["shooting_efficiency"]  # BL-001

@pytest.mark.anyio
async def test_requirement_metric_and_output_ids_survive_typed_intake():
    stub = StubModel([{
        "goal": "best defense", "mode": "quick", "deliverable": "team",
        "required_evidence": ["team_ratings"],
    }, {
        "requirements": [{
            "id": "defense", "description": "lowest defensive rating",
            "capability_options": ["team_ratings"],
            "capability_arguments": {"season": "2025-26"},
            "metric_ids": ["DEF_RATING"],
            "requested_outputs": ["DEF_RATING", "TEAM_NAME"],
        }],
    }])
    task = await ModelIntake(
        stub, provider="stub", model_name="stub", requirement_review=True,
        capability_catalog={"team_ratings": {}},
    ).understand("Which team had the lowest defensive rating in 2025-26?")
    wire = stub.calls[1]["schema"]
    assert wire is RequirementReviewWire
    requirement = next(item for item in task.requirements if item.id == "defense")
    assert requirement.metric_ids == ["DEF_RATING"]
    assert requirement.requested_outputs == ["DEF_RATING", "TEAM_NAME"]


@pytest.mark.parametrize("field", ["metric_ids", "requested_outputs"])
@pytest.mark.parametrize("bad", ["def_rating", "", "1PTS", "A" * 129])
def test_requirement_wire_rejects_malformed_dimension_ids(field, bad):
    from pydantic import ValidationError
    from v2.arguments import CalculationRequirementWire, RequirementWire
    base = {"id": "r", "description": "d", "metric_ids": None, "requested_outputs": None}
    evidence = {**base, "capability_options": ["team_ratings"],
                "capability_argument_sets": [{"capability_id": "team_ratings",
                                              "arguments": {"entries": []}}]}
    for model, row in ((RequirementWire, evidence), (CalculationRequirementWire, base)):
        model.model_validate({**row, field: ["DEF_RATING"]})
        with pytest.raises(ValidationError):
            model.model_validate({**row, field: [bad]})


@pytest.mark.anyio
async def test_planner_subsumes_report_and_shooting_split_requirements():
    task = TaskSpec(
        goal="player line", mode="quick", deliverable="answer",
        requirements=[
            {"id": "line", "description": "season line",
             "capability_options": ["player_report"],
             "capability_arguments": {"player": "luka", "season": "2022-23"}},
            {"id": "shooting", "description": "shooting splits",
             "capability_options": ["shooting_efficiency", "player_report"],
             "capability_arguments": {"player": "luka", "season": "2022-23"}},
        ],
    )
    stub = StubModel([{"nodes": [
        {"id": "report", "description": "full report",
         "capability_hints": ["player_report"],
         "covers_requirement_ids": ["line"],
         "arguments": {"player": "luka", "season": "2022-23"}},
        {"id": "shooting", "description": "shooting splits",
         "capability_hints": ["shooting_efficiency"],
         "covers_requirement_ids": ["shooting"],
         "arguments": {"player": "luka", "season": "2022-23"}},
    ]}])
    plan = await ModelPlanner(
        stub, provider="stub", model_name="stub",
        capability_catalog={"player_report": {}, "shooting_efficiency": {}},
    ).plan(task)
    assert [node.id for node in plan.nodes] == ["report"]
    assert plan.nodes[0].covers_requirement_ids == ["line", "shooting"]

@pytest.mark.anyio
async def test_player_phase_comparison_uses_report_for_regular_and_logs_for_playoffs():
    task = TaskSpec(
        goal="compare player regular season and playoffs", mode="quick",
        deliverable="comparison", requirements=[
            {"id": "regular", "description": "regular season player stats",
             "capability_options": ["game_logs", "player_report"],
             "capability_arguments": {"player": "luka", "season": "2023-24", "playoffs": False}},
            {"id": "playoffs", "description": "playoff player stats",
             "capability_options": ["game_logs"],
             "capability_arguments": {"player": "luka", "season": "2023-24", "playoffs": True}},
        ])
    stub = StubModel([{"nodes": [
        {"id": "regular", "description": "regular logs",
         "capability_hints": ["game_logs"], "covers_requirement_ids": ["regular"],
         "arguments": {"player": "luka", "season": "2023-24", "playoffs": False}},
        {"id": "playoffs", "description": "playoff logs",
         "capability_hints": ["game_logs"], "covers_requirement_ids": ["playoffs"],
         "arguments": {"player": "luka", "season": "2023-24", "playoffs": True}},
    ]}])
    plan = await ModelPlanner(
        stub, provider="stub", model_name="stub",
        capability_catalog={"game_logs": {}, "player_report": {}},
    ).plan(task)
    assert [(node.id, node.capability_hints, node.arguments) for node in plan.nodes] == [
        ("regular", ["player_report"], {"player": "luka", "season": "2023-24"}),
        ("playoffs", ["game_logs"], {"player": "luka", "season": "2023-24", "playoffs": True}),
    ]

@pytest.mark.anyio
async def test_planner_rejects_invalid_replacement_plan_arguments():
    from v2.contracts import TaskSpec
    task = TaskSpec(
        goal="evaluate player", mode="deep_dive", deliverable="report",
        required_evidence=["player_evaluation"], requirements=[{
            "id": "primary", "description": "primary player",
            "capability_options": ["player_evaluation"],
        }],
    )
    catalog = {"player_evaluation": {"description": "player profile", "arguments": {
        "type": "object", "properties": {"player": {"type": "string"}},
        "required": ["player"],
    }}}
    invalid = {"nodes": [{
        "id": "primary", "description": "profile",
        "capability_hints": ["player_evaluation"],
        "covers_requirement_ids": ["primary"], "arguments": {},
    }]}
    planner = ModelPlanner(StubModel([invalid, invalid]), provider="stub",
                           model_name="stub", capability_catalog=catalog)
    with pytest.raises(ValueError,match="required property"):
        await planner.plan(task)

@pytest.mark.anyio
async def test_implicit_relative_season_is_pinned_for_non_prediction_capability():
    from app.tools._core import SEASON
    stub = StubModel([{
        "goal": "three point leaders this season", "mode": "quick",
        "deliverable": "leaders", "season": {
            "value": "2099-00", "source": "default", "confidence": .9,
        }, "required_evidence": ["qualified_leaders"],
    }])
    task = await ModelIntake(
        stub, provider="stub", model_name="stub",
        capability_catalog={"qualified_leaders": {}},
    ).understand("Who are the three point leaders this season?")
    assert task.season.value == SEASON
    assert task.season.source == "default"

@pytest.mark.anyio
async def test_requirement_review_capability_names_in_skills_are_dropped():
    stub = StubModel([{
        "goal": "player playoffs", "mode": "deep_dive", "deliverable": "report",
        "required_evidence": ["game_logs"], "skills": ["game-logs", "roster"],
    }, {
        "requirements": [{"id": "logs", "description": "logs",
                          "capability_options": ["game_logs"]}],
        "missing_skills": ["player-evaluation"],
    }])
    task = await ModelIntake(
        stub, provider="stub", model_name="stub",
        capability_catalog={"game_logs": {}}, requirement_review=True,
    ).understand("How did the player perform in the playoffs?")
    assert task.skills == []
    assert task.required_evidence == ["game_logs"]

@pytest.mark.anyio
async def test_planner_accepts_required_argument_bound_from_parent_entity():
    task = TaskSpec(goal="top player", mode="deep_dive", deliverable="report",
        required_evidence=["player_evaluation"], requirements=[{
            "id":"profile", "description":"profile",
            "capability_options":["player_evaluation"],
            "capability_arguments":{"season":"2025-26"}}])
    catalog = {
        "qualified_leaders":{"arguments":{"type":"object","properties":{}}},
        "player_evaluation":{"arguments":{"type":"object","properties":{
            "player":{"type":"string"},"season":{"type":"string"}},
            "required":["player"]}, "dependent_entity_arguments":{"player":"player"}},
    }
    plan = {"nodes":[
        {"id":"leaders","description":"leaders","capability_hints":["qualified_leaders"]},
        {"id":"profile","description":"profile","depends_on":["leaders"],
         "capability_hints":["player_evaluation"],"covers_requirement_ids":["profile"],
         "arguments":{"season":"2025-26"}},
    ]}
    result = await ModelPlanner(StubModel([plan]), provider="stub", model_name="stub",
                                capability_catalog=catalog).plan(task)
    assert result.nodes[1].arguments == {"season":"2025-26"}

@pytest.mark.anyio
async def test_single_team_rating_rank_does_not_force_player_or_playoff_boards():
    stub = StubModel([{
        "goal": "lowest defense", "mode": "quick", "deliverable": "ranking",
        "skills": ["league-ratings"], "required_evidence": ["team_ratings"],
    }])
    catalog = {name: {} for name in (
        "team_ratings", "player_ratings", "playoff_team_ratings")}
    task = await ModelIntake(
        stub, provider="stub", model_name="stub", capability_catalog=catalog,
    ).understand("Which team has the lowest defensive rating this season?")
    assert task.required_evidence == ["team_ratings"]

@pytest.mark.anyio
async def test_pair_comparison_normalizes_entity_query_list_before_execution():
    from v2.contracts import TaskSpec
    planner = ModelPlanner(
        StubModel([]), provider="stub", model_name="stub",
        capability_catalog={"entity_resolution": {}, "player_comparison": {}},
    )
    task = TaskSpec(goal="compare", mode="quick", deliverable="text")
    plan = __import__('v2.contracts', fromlist=['Plan']).Plan.model_validate({"nodes": [
        {"id":"resolve", "description":"pair", "capability_hints":["entity_resolution"],
         "arguments":{"query":["Myles Turner","Luka Doncic"]}},
        {"id":"compare", "description":"stats", "capability_hints":["player_comparison"],
         "arguments":{"a":"Myles Turner","b":"Luka Doncic"}},
    ]})
    normalized = planner._normalize_plan(task, plan)
    assert normalized.nodes[0].arguments["query"] == "Myles Turner, Luka Doncic"

def test_dependent_player_tool_gets_entity_resolution_parent_when_provider_omits_it():
    from v2.contracts import Plan
    catalog = {
        "entity_resolution": {"arguments": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]}},
        "game_logs": {"arguments": {"type": "object", "properties": {
            "player": {"type": "string"}, "season": {"type": "string"}}},
            "dependent_entity_arguments": {"player": "player"}},
    }
    planner = ModelPlanner(StubModel([]), provider="stub", model_name="stub",
                           capability_catalog=catalog)
    task = TaskSpec(goal="threshold", mode="quick", deliverable="answer")
    plan = Plan.model_validate({"nodes": [{
        "id": "logs", "description": "logs", "capability_hints": ["game_logs"],
        "arguments": {"player": "Tim Hardaway Jr.", "season": "2025-26"},
    }]})
    normalized = planner._normalize_plan(task, plan)
    assert [node.id for node in normalized.nodes] == ["resolve_player", "logs"]
    assert normalized.nodes[0].arguments == {"query": "Tim Hardaway Jr."}
    assert normalized.nodes[1].depends_on == ["resolve_player"]

@pytest.mark.anyio
async def test_team_rank_synthesis_is_deterministic_and_uses_requested_field_only():
    from v2.adapters.models import ModelSynthesizer
    from v2.contracts import EvidenceEnvelope
    task = TaskSpec(goal="lowest turnover", mode="quick", deliverable="team and value",
        requirements=[{"id":"metric","description":"TOV", "capability_options":["team_ratings"],
            "capability_arguments":{"requested_metric":"TM_TOV_PCT","ranking_direction":"asc"}}])
    ev = EvidenceEnvelope(evidence_id="ratings", capability="team_ratings", source="fixture",
        observed_at=datetime.now(UTC), season="2025-26", rows=[
            {"TEAM_NAME":"Oklahoma City Thunder","TM_TOV_PCT":.124,"DEF_RATING":106.5,"TM_TOV_PCT_RANK":1},
            {"TEAM_NAME":"Denver Nuggets","TM_TOV_PCT":.128,"DEF_RATING":116}],
        metric_definitions={"__requested_metric__":"TM_TOV_PCT"},
        qualification="all teams", coverage="full board")
    stub = StubModel([])
    draft = await ModelSynthesizer(stub, provider="stub", model_name="stub").synthesize(task,[ev])
    assert stub.calls == []
    assert len(draft.claims) == 1
    assert draft.claims[0].text == ("Oklahoma City Thunder had the lowest turnover percentage "
                                    "in 2025-26: 0.124.")
    assert "106.5" not in draft.claims[0].text and "12.4" not in draft.claims[0].text

@pytest.mark.anyio
async def test_game_log_aggregate_synthesis_uses_full_population_and_signed_delta():
    from decimal import Decimal
    task = TaskSpec(goal="home away scoring", mode="quick", deliverable="averages counts difference",
        calculation_requirements=[{"id":"difference", "description":"home minus away scoring difference"}])
    def ev(eid, split, total, avg):
        return EvidenceEnvelope(evidence_id=eid, capability="game_logs", source="fixture",
            observed_at=datetime.now(UTC), season="2025-26",
            rows={"player":"Stephen Curry", "filters":f"{split} games", "total":total,
                  "average_pts":Decimal(avg), "matches":[{"pts":Decimal(avg)} for _ in range(total)]})
    stub = StubModel([])
    draft = await ModelSynthesizer(stub, provider="stub", model_name="stub").synthesize(
        task, [ev("home", "home", 23, "25.04347826086956521739130435"),
               ev("away", "away", 20, "28.3")])
    assert stub.calls == []
    assert [claim.text for claim in draft.claims] == [
        "Stephen Curry averaged 25.0 points per game in 23 home games in 2025-26.",
        "Stephen Curry averaged 28.3 points per game in 20 away games in 2025-26.",
        "The home-minus-away scoring difference was -3.3 points per game."]
    assert draft.calculations[-1].result == Decimal("-3.25652173913043478260869565")
    assert all(inp.evidence_id in {"home", "away"} for calc in draft.calculations for inp in calc.inputs)


@pytest.mark.anyio
async def test_pair_synthesis_failure_class_has_deterministic_supported_answer():
    task = TaskSpec(goal="compare players", mode="quick", deliverable="points TS and margin",
        calculation_requirements=[
            {"id":"leader", "description":"identify who scores more"},
            {"id":"margin", "description":"points per game margin difference"}])
    pair = EvidenceEnvelope(evidence_id="pair", capability="player_comparison", source="fixture",
        observed_at=datetime.now(UTC), season="2025-26",
        rows={"a":{"name":"Myles Turner","ppg":11.9},
              "b":{"name":"Luka Dončić","ppg":33.5}})
    turner = EvidenceEnvelope(evidence_id="turner", capability="shooting_efficiency", source="fixture",
        observed_at=datetime.now(UTC), season="2025-26",
        rows={"PLAYER_NAME":"Myles Turner","TS_PCT":58.4})
    luka = EvidenceEnvelope(evidence_id="luka", capability="shooting_efficiency", source="fixture",
        observed_at=datetime.now(UTC), season="2025-26",
        rows={"PLAYER_NAME":"Luka Dončić","TS_PCT":61.6})
    class Down:
        calls = []
        async def generate(self, **call):
            self.calls.append(call)
            raise RuntimeError("all structured-output providers failed")
    down = Down()
    draft = await ModelSynthesizer(down, provider="stub", model_name="stub").synthesize(
        task, [pair, turner, luka])
    assert down.calls == []
    assert [claim.text for claim in draft.claims] == [
        "Myles Turner averaged 11.9 points per game in 2025-26.",
        "Luka Dončić averaged 33.5 points per game in 2025-26.",
        "Luka Dončić scored more points per game than Myles Turner.",
        "Luka Dončić scored 21.6 points per game more than Myles Turner.",
        "Myles Turner had a 58.4% true shooting percentage.",
        "Luka Dončić had a 61.6% true shooting percentage."]
    assert [calc.requirement_id for calc in draft.calculations] == ["ppg_margin"]

@pytest.mark.anyio
async def test_game_log_builder_maps_separate_mean_requirements():
    from decimal import Decimal
    task = TaskSpec(goal="splits", mode="quick", deliverable="all",
        calculation_requirements=[
            {"id":"h","description":"home scoring average"},
            {"id":"a","description":"away scoring average"},
            {"id":"d","description":"home minus away difference"}])
    def ev(eid, split, avg):
        return EvidenceEnvelope(evidence_id=eid, capability="game_logs", source="fixture",
            observed_at=datetime.now(UTC), season="2025-26",
            rows={"player":"Stephen Curry","filters":f"{split} games","total":2,
                  "average_pts":Decimal(avg),"matches":[{"pts":Decimal(avg)},{"pts":Decimal(avg)}]})
    draft = await ModelSynthesizer(StubModel([]), provider="stub", model_name="stub").synthesize(
        task,[ev("home","home","25"),ev("away","away","28")])
    assert [calc.requirement_id for calc in draft.calculations] == ["home_mean","away_mean","home_away_delta"]


@pytest.mark.anyio
async def test_pair_builder_maps_ppg_and_ts_difference_without_duplicate_ids():
    task = TaskSpec(goal="compare", mode="quick", deliverable="differences",
        calculation_requirements=[
            {"id":"p","description":"points per game difference"},
            {"id":"t","description":"true shooting percentage difference"}])
    pair = EvidenceEnvelope(evidence_id="pair", capability="player_comparison", source="fixture",
        observed_at=datetime.now(UTC), season="2025-26",
        rows={"a":{"name":"Myles Turner","ppg":11.9},"b":{"name":"Luka Dončić","ppg":33.5}})
    def ts(eid,name,value):
        return EvidenceEnvelope(evidence_id=eid, capability="shooting_efficiency", source="fixture",
            observed_at=datetime.now(UTC), season="2025-26",rows={"PLAYER_NAME":name,"TS_PCT":value})
    draft = await ModelSynthesizer(StubModel([]), provider="stub", model_name="stub").synthesize(
        task,[pair,ts("mt","Myles Turner",58.4),ts("ld","Luka Dončić",61.6)])
    assert [calc.requirement_id for calc in draft.calculations] == ["ppg_margin","ts_margin"]
    assert len({calc.requirement_id for calc in draft.calculations}) == 2

@pytest.mark.anyio
async def test_canonicalizer_creates_split_requirements_from_deliverable():
    from v2.adapters.models import _canonicalize_calculation_requirements
    task = TaskSpec(goal="Curry splits", mode="quick",
        deliverable="home and away means, sample sizes, and home-minus-away delta",
        requirements=[{"id":"logs","description":"logs","capability_options":["game_logs"]}])
    normalized = _canonicalize_calculation_requirements(task)
    assert [(x.id,x.description) for x in normalized.calculation_requirements] == [
        ("home_mean","Canonical home points-per-game mean"),
        ("away_mean","Canonical away points-per-game mean"),
        ("home_away_delta","Canonical home-minus-away points-per-game difference")]


def test_canonicalizer_wording_permutations_produce_identical_split_kinds():
    from v2.adapters.models import _canonicalize_calculation_requirements
    variants = [
        ["Stephen Curry's home scoring average (PPG) for 2025-26",
         "Stephen Curry's away scoring average (PPG) for 2025-26",
         "Difference between home and away scoring average for Stephen Curry in 2025-26"],
        ["Calculate home-minus-away scoring difference"],
        [],
    ]
    outputs=[]
    for descriptions in variants:
        task=TaskSpec(goal="Compare home and away scoring",mode="quick",
            deliverable="each average, sample size, and home-minus-away difference",
            requirements=[{"id":"logs","description":"logs","capability_options":["game_logs"]}],
            calculation_requirements=[{"id":f"r{i}","description":d} for i,d in enumerate(descriptions)])
        outputs.append([x.description for x in _canonicalize_calculation_requirements(task).calculation_requirements])
    assert outputs[0] == outputs[1] == outputs[2]


def test_draft_validator_rejects_duplicate_requirement_ownership():
    from v2.adapters.models import _validate_draft
    from v2.contracts import DraftReport
    task=TaskSpec(goal="x",mode="quick",deliverable="x",
        calculation_requirements=[{"id":"same","description":"one"}])
    with pytest.raises(ValueError, match="must not duplicate requirement ids"):
        DraftReport.model_validate({"sections":[],"claims":[],"calculations":[
            {"calculation_id":"a","requirement_id":"same","operation":"mean",
             "inputs":[{"evidence_id":"e","path":"rows.x"}],"result":1},
            {"calculation_id":"b","requirement_id":"same","operation":"mean",
             "inputs":[{"evidence_id":"e","path":"rows.y"}],"result":2}]})

@pytest.mark.anyio
async def test_sample_size_calc_artifacts_are_observed_not_blocked():
    from v2.adapters.models import _canonicalize_calculation_requirements
    task=TaskSpec(goal="home away scoring",mode="quick",deliverable="averages sample sizes and difference",
        requirements=[{"id":"logs","description":"logs","capability_options":["game_logs"]}],
        calculation_requirements=[
            {"id":"h","description":"Home scoring average points per game."},
            {"id":"a","description":"Away scoring average points per game."},
            {"id":"hs","description":"Home sample size (number of games)."},
            {"id":"as","description":"Away sample size (number of games)."},
            {"id":"d","description":"Home-minus-away scoring difference."}])
    normalized=_canonicalize_calculation_requirements(task)
    assert [x.id for x in normalized.calculation_requirements] == ["home_mean","away_mean","home_away_delta"]


@pytest.mark.parametrize("raw,shown", [(0.584,"58.4%"),(58.4,"58.4%")])
@pytest.mark.anyio
async def test_pair_ts_projection_normalizes_fraction_and_percent(raw,shown):
    task=TaskSpec(goal="compare points",mode="quick",deliverable="PPG difference",
        calculation_requirements=[{"id":"d","description":"PPG difference"}])
    pair=EvidenceEnvelope(evidence_id="p",capability="player_comparison",source="f",observed_at=datetime.now(UTC),season="2025-26",rows={"a":{"name":"A","ppg":1},"b":{"name":"B","ppg":2}})
    ts=EvidenceEnvelope(evidence_id="t",capability="shooting_efficiency",source="f",observed_at=datetime.now(UTC),rows={"PLAYER_NAME":"A","TS_PCT":raw})
    draft=await ModelSynthesizer(StubModel([]),provider="stub",model_name="stub").synthesize(task,[pair,ts])
    assert any(shown in claim.text for claim in draft.claims)

@pytest.mark.anyio
async def test_intake_primary_transient_retries_then_succeeds(monkeypatch):
    from v2.adapters.models import ProviderStructuredModel
    from v2.runtime import RequestEnvelope
    calls=[]
    class A:
        def __init__(self,*a,**k):pass
        async def run(self,prompt):
            calls.append(prompt)
            if len(calls)==1: raise TimeoutError("temporary")
            return type("R",(),{"output":TaskSpec(goal="ok",mode="quick",deliverable="x")})()
    class M:model_name="primary"
    monkeypatch.setattr("v2.adapters.models.Agent",A);monkeypatch.setattr("v2.adapters.models.random.uniform",lambda a,b:0)
    m=ProviderStructuredModel("inception","primary");monkeypatch.setattr(m,"_models",lambda:[("inception",M())])
    e=RequestEnvelope.freeze(provider="inception",model="primary",route="intake",prompt="p",context={},tool_schemas={},planner_version="v2")
    out=await m.generate(schema=TaskSpec,prompt="p",payload={"same":"input"},envelope=e)
    assert out.goal=="ok" and len(calls)==2
    assert [(x["attempt_number"],x["message_class"]) for x in m.last_failures]==[(1,"timeout")]


@pytest.mark.anyio
async def test_intake_primary_exhausted_then_secondary_success(monkeypatch):
    from v2.adapters.models import ProviderStructuredModel
    from v2.runtime import RequestEnvelope
    calls=[]
    class A:
        def __init__(self,model,*a,**k):self.model=model
        async def run(self,prompt):
            calls.append((self.model.model_name,prompt))
            if self.model.model_name=="primary":raise TimeoutError("temporary")
            return type("R",(),{"output":TaskSpec(goal="ok",mode="quick",deliverable="x")})()
    class M:
        def __init__(self,n):self.model_name=n
    monkeypatch.setattr("v2.adapters.models.Agent",A);monkeypatch.setattr("v2.adapters.models.random.uniform",lambda a,b:0)
    m=ProviderStructuredModel("inception","primary");monkeypatch.setattr(m,"_models",lambda:[("inception",M("primary")),("mistral",M("secondary"))])
    e=RequestEnvelope.freeze(provider="inception",model="primary",route="intake",prompt="p",context={},tool_schemas={},planner_version="v2")
    await m.generate(schema=TaskSpec,prompt="p",payload={"same":"input"},envelope=e)
    assert [x[0] for x in calls]==["primary","primary","secondary"]
    assert m.last_provider=="mistral" and m.last_model=="mistral_free_limit:secondary"


@pytest.mark.anyio
async def test_intake_schema_failure_does_not_outer_retry(monkeypatch):
    from pydantic import ValidationError
    from v2.adapters.models import ProviderStructuredModel
    from v2.runtime import RequestEnvelope
    calls=[]
    class A:
        def __init__(self,model,*a,**k):self.model=model
        async def run(self,prompt):
            calls.append(self.model.model_name)
            if self.model.model_name=="primary":TaskSpec.model_validate({"goal":""})
            return type("R",(),{"output":TaskSpec(goal="ok",mode="quick",deliverable="x")})()
    class M:
        def __init__(self,n):self.model_name=n
    monkeypatch.setattr("v2.adapters.models.Agent",A)
    m=ProviderStructuredModel("inception","primary");monkeypatch.setattr(m,"_models",lambda:[("inception",M("primary")),("mistral",M("secondary"))])
    e=RequestEnvelope.freeze(provider="inception",model="primary",route="intake",prompt="p",context={},tool_schemas={},planner_version="v2")
    await m.generate(schema=TaskSpec,prompt="p",payload={},envelope=e)
    assert calls==["primary","secondary"]
    assert m.last_failures[0]["message_class"]=="structured_output"

@pytest.mark.anyio
async def test_recorded_intake_ledger_carries_provider_attempt_diagnostics():
    from v2.adapters import RecordedStructuredModel
    from v2.runtime import RequestEnvelope, RunLedger
    class M:
        last_provider="secondary";last_model="backup"
        last_failures=[{"route":"intake","provider":"primary","model":"main","attempt_number":1,
            "exception_type":"TimeoutError","message_class":"timeout","latency_ms":12}]
        async def generate(self,**call):return TaskSpec(goal="ok",mode="quick",deliverable="x")
    envelope=RequestEnvelope.freeze(provider="primary",model="main",route="intake",prompt="p",context={},tool_schemas={},planner_version="v2")
    ledger=RunLedger("run")
    await RecordedStructuredModel(M(),ledger,turn_id="turn").generate(schema=TaskSpec,prompt="p",payload={},envelope=envelope)
    attempt=ledger.entries[-1].data
    assert attempt["provider_attempts"]==M.last_failures
    assert attempt["used_fallback"] is True

@pytest.mark.anyio
async def test_intake_global_deadline_stops_many_provider_chain(monkeypatch):
    from v2.adapters.models import ProviderStructuredModel
    from v2.runtime import RequestEnvelope
    calls=[]; clock=type("Clock",(),{"value":0})()
    class A:
        def __init__(self,model,*a,**k):self.model=model
        async def run(self,prompt):
            calls.append(self.model.model_name);clock.value += 7;raise TimeoutError("x")
    class M:
        def __init__(self,n):self.model_name=n
    monkeypatch.setattr("v2.adapters.models.Agent",A)
    monkeypatch.setattr("v2.adapters.models.time.monotonic",lambda:clock.value)
    monkeypatch.setattr("v2.adapters.models.time.perf_counter",lambda:0)
    monkeypatch.setattr("v2.adapters.models.random.uniform",lambda a,b:0)
    models=[("inception",M("m0")),("mistral",M("m1")),("groq",M("m2")),("openrouter",M("m3"))]
    m=ProviderStructuredModel("inception","m0");monkeypatch.setattr(m,"_models",lambda:models)
    e=RequestEnvelope.freeze(provider="inception",model="m0",route="intake",prompt="p",context={},tool_schemas={},planner_version="v2")
    with pytest.raises(RuntimeError,match="intake_deadline"):
        await m.generate(schema=TaskSpec,prompt="p",payload={},envelope=e)
    assert calls==["m0","m0","m1"]
    assert m.last_failures[-1]["message_class"]=="intake_deadline"


@pytest.mark.anyio
async def test_exhausted_intake_ledger_keeps_complete_attempt_diagnostics():
    from v2.adapters import RecordedStructuredModel
    from v2.runtime import RequestEnvelope,RunLedger
    diagnostics=[{"route":"intake","provider":"p","model":"m","attempt_number":1,"exception_type":"TimeoutError","message_class":"timeout","latency_ms":6},
                 {"route":"intake","provider":"intake","model":"deadline","attempt_number":2,"exception_type":"TimeoutError","message_class":"intake_deadline","latency_ms":0}]
    class M:
        last_failures=diagnostics
        async def generate(self,**call):raise RuntimeError("all structured-output providers failed")
    e=RequestEnvelope.freeze(provider="p",model="m",route="intake",prompt="p",context={},tool_schemas={},planner_version="v2")
    ledger=RunLedger("run")
    with pytest.raises(RuntimeError):
        await RecordedStructuredModel(M(),ledger,turn_id="turn").generate(schema=TaskSpec,prompt="p",payload={},envelope=e)
    assert ledger.entries[-1].data["provider_attempts"]==diagnostics
    assert len(ledger.entries)==2

@pytest.mark.anyio
async def test_requirement_review_exhaustion_preserves_intake_without_blocker():
    class ReviewDown:
        calls=0
        async def generate(self,**call):
            self.calls+=1
            if self.calls==1:
                return TaskSpec(goal="pair",mode="quick",deliverable="answer",
                    entities=[
                        {"id":"myles-turner","type":"player","display_name":"Myles Turner"},
                        {"id":"luka-doncic","type":"player","display_name":"Luka Doncic"}],
                    season={"value":"2025-26","source":"user","confidence":1.0},
                    required_evidence=["player_comparison"])
            raise RuntimeError("all structured-output providers failed [x]")
    model=ReviewDown()
    task=await ModelIntake(model,provider="stub",model_name="stub",
        capability_catalog={"player_comparison":{}},requirement_review=True).understand("pair")
    assert task.required_evidence==["player_comparison"]
    assert len(task.requirements)==1
    assert task.requirements[0].capability_options==["player_comparison"]
    assert task.requirements[0].id=="required_player_comparison"
    assert task.requirements[0].capability_arguments=={
        "a":"Myles Turner","b":"Luka Doncic","season":"2025-26"}
    assert task.open_questions==[]
    assert model.calls==2


def test_route_policy_table_bounds_model_owned_routes():
    from v2.adapters.models import ROUTE_POLICIES
    assert ROUTE_POLICIES["requirement_review"]["total_budget_s"] <= 12
    assert ROUTE_POLICIES["planner"]["total_budget_s"] <= 12
    assert ROUTE_POLICIES["synthesizer"]["deterministic_fallback"] is True
    assert ROUTE_POLICIES["semantic_verifier"]["deterministic_fallback"] is True

@pytest.mark.anyio
async def test_run_model_deadline_is_shared_across_sequential_routes(monkeypatch):
    from v2.adapters.models import ProviderStructuredModel
    from v2.runtime import RequestEnvelope
    from v2.runtime.budget import RUN_MODEL_DEADLINE
    clock=type("Clock",(),{"value":0})();calls=[]
    class A:
        def __init__(self,model,*a,**k):self.model=model
        async def run(self,prompt):
            calls.append(self.model.model_name);clock.value += 7;raise TimeoutError("x")
    class M:model_name="m"
    monkeypatch.setattr("v2.adapters.models.Agent",A)
    monkeypatch.setattr("v2.adapters.models.time.monotonic",lambda:clock.value)
    monkeypatch.setattr("v2.adapters.models.time.perf_counter",lambda:0)
    monkeypatch.setattr("v2.adapters.models.random.uniform",lambda a,b:0)
    RUN_MODEL_DEADLINE.set(20)
    m=ProviderStructuredModel("inception","m");monkeypatch.setattr(m,"_models",lambda:[("inception",M())])
    def env(route):return RequestEnvelope.freeze(provider="inception",model="m",route=route,prompt="p",context={},tool_schemas={},planner_version="v2")
    with pytest.raises(RuntimeError):await m.generate(schema=TaskSpec,prompt="p",payload={},envelope=env("intake"))
    with pytest.raises(RuntimeError):await m.generate(schema=TaskSpec,prompt="p",payload={},envelope=env("planner"))
    assert clock.value==21
    assert len(calls)==3
    assert m.last_failures[-1]["message_class"]=="planner_deadline"

@pytest.mark.anyio
async def test_review_combined_home_away_requirement_expands_before_planning():
    stub=StubModel([{"goal":"splits","mode":"quick","deliverable":"home and away averages",
        "entities":[{"id":"curry","type":"player","display_name":"Stephen Curry"}]},
        {"requirements":[{"id":"combined","description":"combined splits","capability_options":["game_logs"],"capability_arguments":{"player":"Stephen Curry","season":"2025-26","home_away":None}}]}])
    task=await ModelIntake(stub,provider="stub",model_name="stub",capability_catalog={"game_logs":{}},requirement_review=True).understand("Compare home and away")
    assert [(r.id,r.capability_arguments["home_away"]) for r in task.requirements]==[("combined_home","home"),("combined_away","away")]


def test_verifier_prompt_closes_completeness_over_requested_metrics_only():
    from v2.prompts import load_prompt
    p=load_prompt("verifier")
    assert "Never demand a metric merely because evidence happens to contain it" in p
    assert "FG3_PCT" in p

@pytest.mark.anyio
async def test_model_valid_path_wrong_result_remains_for_mechanical_rejection():
    task=TaskSpec(goal="delta",mode="quick",deliverable="delta",calculation_requirements=[{"id":"d","description":"delta"}])
    ev=EvidenceEnvelope(evidence_id="e",capability="x",source="f",observed_at=datetime.now(UTC),rows={"a":2,"b":1})
    stub=StubModel([{"sections":[],"claims":[{"text":"Difference 99.","kind":"derived","evidence_ids":["e"],"calculation_id":"bad"}],"calculations":[{"calculation_id":"bad","requirement_id":"d","operation":"subtract","inputs":[{"evidence_id":"e","path":"rows.a"},{"evidence_id":"e","path":"rows.b"}],"result":99}]}])
    draft=await ModelSynthesizer(stub,provider="s",model_name="s").synthesize(task,[ev])
    assert draft.calculations[0].result==99
    from v2.domain.calculations import Calculation
    from v2.runtime.verifier import verify_mechanical
    calculation=Calculation.model_validate({key:value for key,value in draft.calculations[0].model_dump().items() if key != "requirement_id"})
    report=verify_mechanical(task,draft,[ev],[calculation])
    assert report.status.value=="repair"
    assert any("does not recompute" in reason for reason in report.claim_results[0].reasons)


def test_calculation_validation_accepts_ordinary_rate_rounding_but_not_wrong_value():
    from v2.domain.calculations import Calculation, validate_calculation
    from v2.domain.evidence import EvidenceIndex
    ev=EvidenceEnvelope(evidence_id="rate",capability="leaders",source="fixture",observed_at=datetime.now(UTC),rows={"total":200,"gp":64})
    base={"calculation_id":"bpg","operation":"divide","inputs":[{"evidence_id":"rate","path":"rows.total"},{"evidence_id":"rate","path":"rows.gp"}]}
    rounded=Calculation.model_validate({**base,"result":"3.1"})
    wrong=Calculation.model_validate({**base,"result":"99"})
    index=EvidenceIndex([ev])
    assert validate_calculation(rounded,index) is None
    assert "does not recompute" in validate_calculation(wrong,index)

@pytest.mark.anyio
async def test_followup_accepts_only_explicit_verified_antecedent_types():
    from v2.contracts import ConversationTurn
    stub=StubModel([{"goal":"compare Victor Wembanyama with San Antonio Spurs","mode":"quick","deliverable":"answer",
        "entities":[{"id":"wemby","type":"player","display_name":"Victor Wembanyama"},{"id":"sas","type":"team","display_name":"San Antonio Spurs"}]}])
    intake=ModelIntake(stub,**stage_kwargs())
    task=await intake.understand("How does that player compare with that team?",context=(
        ConversationTurn(role="assistant",content="Victor Wembanyama leads for the San Antonio Spurs."),))
    assert task.open_questions==[]
    assert {e.type for e in task.entities}=={"player","team"}

class AdmissionModel:
    def __init__(self, task, review_factory):
        self.task = task
        self.review_factory = review_factory
        self.calls = []

    async def generate(self, **call):
        self.calls.append(call)
        if call["envelope"].route == "intake":
            return call["schema"].model_validate(self.task)
        if call["envelope"].route == "intake_admission":
            return call["schema"].model_validate(
                self.review_factory(call["payload"]))
        raise AssertionError(call["envelope"].route)


def admission_stage_kwargs():
    return {**stage_kwargs(), "intake_admission": True}


def blocked_reference(payload, text, kind="unknown", *, source="request", turn=None):
    body = (payload["question"] if source == "request" else
            payload["conversation_context"][turn]["content"])
    start = body.index(text)
    return {"target": payload["target"], "decision": "block",
            "expected_subjects": payload["expected_subjects"],
            "unresolved_references": [{"kind": kind, "locator": {
                "source": source, "context_turn": turn, "start": start,
                "end": start + len(text), "text": text}}]}


def blocked_subject(payload, index=0):
    return {"target": payload["target"], "decision": "block",
            "expected_subjects": payload["expected_subjects"],
            "findings": [{"code": "subject_mismatch",
                "affected_subjects": [payload["expected_subjects"][index]]}]}


def admitted(payload, spans):
    bindings=[]
    for subject, span in zip(payload["expected_subjects"], spans, strict=True):
        source, turn, text = span
        body = (payload["question"] if source == "request" else
                payload["conversation_context"][turn]["content"])
        start=body.index(text)
        bindings.append({"subject":subject,"locator":{"source":source,
            "context_turn":turn,"start":start,"end":start+len(text),"text":text}})
    return {"target":payload["target"],"decision":"admit",
            "expected_subjects":payload["expected_subjects"],"bindings":bindings}


@pytest.mark.anyio
@pytest.mark.parametrize("user_text", ["How did he do?", "How did they compare?"])
async def test_pronoun_only_empty_context_returns_typed_unresolved_reference(user_text):
    model=AdmissionModel({"goal":"performance","mode":"quick","deliverable":"answer",
        "entities":[{"id":"unresolved","type":"league","display_name":"Unresolved subject"}]},
        lambda payload: blocked_reference(payload, "he" if "he" in user_text else "they"))
    task=await ModelIntake(model,**admission_stage_kwargs()).understand(user_text)
    assert task.entities==[] and task.required_evidence==[]
    assert task.open_questions and "unresolved reference" in task.open_questions[-1]
    assert [call["envelope"].route for call in model.calls]==["intake","intake_admission"]


@pytest.mark.anyio
async def test_explicit_player_context_does_not_license_invented_team():
    from v2.contracts import ConversationTurn
    model=AdmissionModel({"goal":"compare","mode":"quick","deliverable":"answer",
        "entities":[{"id":"w","type":"player","display_name":"Victor Wembanyama"},
                    {"id":"t","type":"team","display_name":"Invented Team"}]},
        lambda payload: blocked_subject(payload,2))
    task=await ModelIntake(model,**admission_stage_kwargs()).understand(
        "Compare that player with that team.",context=(
            ConversationTurn(role="assistant",content="Victor Wembanyama led the board."),))
    assert task.entities==[] and "subject_mismatch" in task.open_questions


@pytest.mark.anyio
@pytest.mark.parametrize("bad", [
 {"goal":"NBA assists leaders","mode":"quick","deliverable":"top assists",
  "entities":[{"id":"assists","type":"league","display_name":"NBA assists"}]},
 {"goal":"compare Curry and Durant","mode":"quick","deliverable":"comparison",
  "entities":[{"id":"curry","type":"player","display_name":"Curry"}]},
 {"goal":"blocks leaders","mode":"quick","deliverable":"rank blocks",
  "season":{"value":"2026-27","source":"default","confidence":1.0}},
])
async def test_intake_semantic_anchor_mismatch_is_blocked_by_typed_review(bad):
    model=AdmissionModel(bad,blocked_subject)
    task=await ModelIntake(model,**admission_stage_kwargs()).understand(
        "Who led blocks in 2025-26?")
    assert task.entities==[] and task.required_evidence==[]
    assert "subject_mismatch" in task.open_questions


@pytest.mark.anyio
async def test_explicit_lebron_possessive_is_admitted_without_referent_false_positive():
    request="Analyze LeBron James and his fit."
    model=AdmissionModel({"goal":"analyze LeBron fit","mode":"quick","deliverable":"fit",
        "entities":[{"id":"2544","type":"player","display_name":"LeBron James"}],
        "requirements":[{"id":"fit","description":"fit","capability_options":["standings"],
                         "requested_outputs":["FIT_ASSESSMENT"]}]},
        lambda payload: admitted(payload,[("request",None,"Analyze LeBron James and his fit."),
                                          ("request",None,"LeBron James"),
                                          ("request",None,"fit"),
                                          ("request",None,"fit")]))
    task=await ModelIntake(model,**admission_stage_kwargs()).understand(request)
    assert [(e.id,e.display_name) for e in task.entities]==[("2544","LeBron James")]
    assert task.open_questions==[]


@pytest.mark.anyio
async def test_unicode_paraphrase_and_context_locator_are_admitted():
    from v2.contracts import ConversationTurn
    context=(ConversationTurn(role="assistant",content="Nikola Jokić led Denver."),)
    model=AdmissionModel({"goal":"summarize center impact","mode":"quick","deliverable":"impact",
        "entities":[{"id":"203999","type":"player","display_name":"Nikola Jokić"}]},
        lambda payload: admitted(payload,[("request",None,"What about the center’s impact?"),
                                          ("context",0,"Nikola Jokić")]))
    task=await ModelIntake(model,**admission_stage_kwargs()).understand(
        "What about the center’s impact?",context=context)
    assert task.entities[0].display_name=="Nikola Jokić" and not task.open_questions


@pytest.mark.anyio
async def test_copied_goal_cannot_mask_wrong_typed_requirement():
    task={"goal":"Show LeBron James points","mode":"quick","deliverable":"points",
          "entities":[{"id":"2544","type":"player","display_name":"LeBron James"}],
          "metric_ids":["AST"], "requested_outputs":["AST"],
          "requirements":[{"id":"wrong","description":"assists","capability_options":["standings"],
                           "metric_ids":["AST"],"requested_outputs":["AST"]}]}
    model=AdmissionModel(task,lambda payload: blocked_subject(payload,2))
    result=await ModelIntake(model,**admission_stage_kwargs()).understand(
        "Show LeBron James points.")
    assert result.requirements==[] and "subject_mismatch" in result.open_questions

@pytest.mark.anyio
async def test_explicit_context_entity_performance_summary_passes():
    stub=StubModel([{"goal":"summarize Victor Wembanyama performance","mode":"quick","deliverable":"performance summary","entities":[{"id":"w","type":"player","display_name":"Victor Wembanyama"}]}])
    task=await ModelIntake(stub,**stage_kwargs()).understand("Summarize Victor Wembanyama's performance")
    assert len(stub.calls)==1 and task.entities[0].display_name=="Victor Wembanyama"

@pytest.mark.anyio
async def test_team_rank_deterministic_draft_satisfies_rank_calculation_requirement():
    from v2.adapters.models import ModelSynthesizer
    from v2.contracts import EvidenceEnvelope
    task = TaskSpec(goal="lowest defense", mode="quick", deliverable="team and value",
        requirements=[{"id":"metric","description":"def rating", "capability_options":["team_ratings"],
            "capability_arguments":{"requested_metric":"DEF_RATING","ranking_direction":"asc"}}],
        calculation_requirements=[{"id":"lowest_def_rating_lookup",
            "description":"Identify the team with the minimum defensive rating and extract its value.",
            "metric_ids":["DEF_RATING"]}])
    ev = EvidenceEnvelope(evidence_id="ratings", capability="team_ratings", source="fixture",
        observed_at=datetime.now(UTC), season="2025-26", rows=[
            {"TEAM_NAME":"Oklahoma City Thunder","DEF_RATING":106.5},
            {"TEAM_NAME":"Detroit Pistons","DEF_RATING":108.9},
            {"TEAM_NAME":"San Antonio Spurs","DEF_RATING":110.4}],
        metric_definitions={"__requested_metric__":"DEF_RATING"})
    stub = StubModel([])
    draft = await ModelSynthesizer(stub, provider="stub", model_name="stub").synthesize(task,[ev])
    assert stub.calls == []
    assert draft.claims[0].text == ("Oklahoma City Thunder had the lowest defensive rating "
                                    "in 2025-26: 106.5.")
    assert draft.claims[0].kind.value == "derived"
    assert draft.calculations[0].requirement_id == "lowest_def_rating_lookup"
    assert draft.calculations[0].operation == "rank_asc"
    assert draft.calculations[0].result == 1
    assert draft.blocked_calculation_requirement_ids == []

@pytest.mark.anyio
@pytest.mark.parametrize("rows,direction,description,metric_ids,expected_team,expected_subject,blocked", [
    ([{"TEAM_NAME":"Detroit Pistons","DEF_RATING":108.9}, {"TEAM_NAME":"Oklahoma City Thunder","DEF_RATING":106.5}], "asc", "Identify the team with the minimum defensive rating.", ["DEF_RATING"], "Oklahoma City Thunder", 1, False),
    ([{"TEAM_NAME":"Null Team","DEF_RATING":None}, {"TEAM_NAME":"Oklahoma City Thunder","DEF_RATING":106.5}, {"TEAM_NAME":"Detroit Pistons","DEF_RATING":108.9}], "asc", "Identify the team with the lowest defensive rating.", ["DEF_RATING"], "Oklahoma City Thunder", 0, False),
    ([{"TEAM_NAME":"Low","TS_PCT":.55}, {"TEAM_NAME":"High","TS_PCT":.61}], "desc", "Identify the true shooting percentage leader.", ["TS_PCT"], "High", 1, False),
    ([{"TEAM_NAME":"Low","DEF_RATING":106.5}, {"TEAM_NAME":"High","DEF_RATING":108.9}], "asc", "Identify the team with the maximum defensive rating.", ["OFF_RATING"], "Low", None, True),
    ([{"TEAM_NAME":"Low","DEF_RATING":106.5}, {"TEAM_NAME":"High","DEF_RATING":108.9}], "asc", "Identify the team average salary.", [], "Low", None, True),
    ([{"TEAM_NAME":"Low","DEF_RATING":106.5}, {"TEAM_NAME":"Detroit Pistons","DEF_RATING":108.9}], "asc", "What rank is Detroit by defensive rating?", [], "Low", None, True),
])
async def test_team_rank_calculation_adversarial(rows,direction,description,metric_ids,expected_team,expected_subject,blocked):
    from v2.adapters.models import ModelSynthesizer
    from v2.contracts import EvidenceEnvelope
    metric = "TS_PCT" if any("TS_PCT" in row for row in rows) else "DEF_RATING"
    task = TaskSpec(goal="rating leader", mode="quick", deliverable="team and value",
        requirements=[{"id":"metric","description":"rating", "capability_options":["team_ratings"],
            "capability_arguments":{"requested_metric":metric,"ranking_direction":direction}}],
        calculation_requirements=[{"id":"calc", "description":description, "metric_ids":metric_ids}])
    ev = EvidenceEnvelope(evidence_id="ratings", capability="team_ratings", source="fixture",
        observed_at=datetime.now(UTC), season="2025-26", rows=rows,
        metric_definitions={"__requested_metric__":metric})
    draft = await ModelSynthesizer(StubModel([]),provider="stub",model_name="stub").synthesize(task,[ev])
    assert expected_team in draft.claims[0].text
    if blocked:
        assert draft.calculations == [] and draft.blocked_calculation_requirement_ids == ["calc"]
        assert draft.claims[0].kind.value == "observed"
    else:
        assert draft.calculations[0].subject_input == expected_subject
        assert draft.calculations[0].result == 1
        assert draft.claims[0].calculation_id == draft.calculations[0].calculation_id

@pytest.mark.anyio
async def test_team_rank_typed_metric_ids_own_ranked_calculations():
    from v2.adapters.models import ModelSynthesizer
    from v2.contracts import EvidenceEnvelope
    task=TaskSpec(goal="lowest defense",mode="quick",deliverable="team",
        requirements=[{"id":"metric","description":"defense","capability_options":["team_ratings"],"capability_arguments":{"requested_metric":"DEF_RATING","ranking_direction":"asc"}}],
        calculation_requirements=[{"id":"low","description":"minimum defensive rating","metric_ids":["DEF_RATING"]},
                                  {"id":"high","description":"maximum defensive rating","metric_ids":["DEF_RATING"]}])
    ev=EvidenceEnvelope(evidence_id="r",capability="team_ratings",source="fixture",observed_at=datetime.now(UTC),season="2025-26",rows=[{"TEAM_NAME":"High","DEF_RATING":110},{"TEAM_NAME":"Low","DEF_RATING":100}],metric_definitions={"__requested_metric__":"DEF_RATING"})
    draft=await ModelSynthesizer(StubModel([]),provider="stub",model_name="stub").synthesize(task,[ev])
    assert [c.requirement_id for c in draft.calculations]==["low","high"]
    assert draft.calculations[0].subject_input==1

@pytest.mark.anyio
async def test_team_rank_tie_fails_closed():
    from v2.adapters.models import ModelSynthesizer
    from v2.contracts import EvidenceEnvelope
    task=TaskSpec(goal="lowest defense",mode="quick",deliverable="team",requirements=[{"id":"metric","description":"defense","capability_options":["team_ratings"],"capability_arguments":{"requested_metric":"DEF_RATING","ranking_direction":"asc"}}],calculation_requirements=[{"id":"low","description":"minimum defensive rating"}])
    ev=EvidenceEnvelope(evidence_id="r",capability="team_ratings",source="fixture",observed_at=datetime.now(UTC),rows=[{"TEAM_NAME":"A","DEF_RATING":100},{"TEAM_NAME":"B","DEF_RATING":100}],metric_definitions={"__requested_metric__":"DEF_RATING"})
    draft=await ModelSynthesizer(StubModel([]),provider="stub",model_name="stub").synthesize(task,[ev])
    assert draft.claims==[] and draft.calculations==[]
    assert draft.blocked_calculation_requirement_ids==["low"]
    assert "tied" in draft.gaps[0]

@pytest.mark.anyio
@pytest.mark.parametrize("description", [
    "Determine whether Detroit has the minimum defensive rating.",
    "Is Detroit the team with the lowest defensive rating?",
    "Compare Detroit to the defensive-rating minimum.",
])
async def test_team_entity_extremum_requirements_fail_closed_without_typed_global_scope(description):
    from v2.adapters.models import ModelSynthesizer
    from v2.contracts import EntityRef, EvidenceEnvelope
    from v2.domain.calculations import Calculation
    from v2.runtime.verifier import verify_mechanical
    task=TaskSpec(goal=description,mode="quick",deliverable="answer",
        entities=[EntityRef(type="team",id="DET",display_name="Detroit Pistons")],
        requirements=[{"id":"metric","description":"defense board","capability_options":["team_ratings"],"capability_arguments":{"requested_metric":"DEF_RATING","ranking_direction":"asc"}}],
        calculation_requirements=[{"id":"scope","description":description}])
    ev=EvidenceEnvelope(evidence_id="r",capability="team_ratings",source="fixture",observed_at=datetime.now(UTC),season="2025-26",qualification="all teams",coverage="full board",rows=[{"TEAM_NAME":"Detroit Pistons","DEF_RATING":108.9},{"TEAM_NAME":"Oklahoma City Thunder","DEF_RATING":106.5}],metric_definitions={"__requested_metric__":"DEF_RATING"})
    draft=await ModelSynthesizer(StubModel([]),provider="stub",model_name="stub").synthesize(task,[ev])
    assert draft.calculations==[] and draft.blocked_calculation_requirement_ids==["scope"]
    assert draft.claims[0].calculation_id is None
    result=verify_mechanical(task,draft,[ev],[])
    assert result.status.value != "pass"

@pytest.mark.anyio
async def test_team_rank_eligible_unsorted_draft_passes_mechanical_verifier():
    from v2.adapters.models import ModelSynthesizer
    from v2.contracts import EvidenceEnvelope
    from v2.domain.calculations import Calculation
    from v2.runtime.verifier import verify_mechanical
    task=TaskSpec(goal="lowest defense",mode="quick",deliverable="team and value",
        requirements=[{"id":"metric","description":"full defensive rating board","capability_options":["team_ratings"],"capability_arguments":{"requested_metric":"DEF_RATING","ranking_direction":"asc"}}],
        calculation_requirements=[{"id":"low","description":"minimum defensive rating","metric_ids":["DEF_RATING"]}])
    ev=EvidenceEnvelope(evidence_id="r",capability="team_ratings",source="fixture",observed_at=datetime.now(UTC),season="2025-26",qualification="all teams",coverage="full board",rows=[{"TEAM_NAME":"Detroit Pistons","DEF_RATING":108.9},{"TEAM_NAME":"Oklahoma City Thunder","DEF_RATING":106.5},{"TEAM_NAME":"San Antonio Spurs","DEF_RATING":110.4}],metric_definitions={"__requested_metric__":"DEF_RATING"})
    draft=await ModelSynthesizer(StubModel([]),provider="stub",model_name="stub").synthesize(task,[ev])
    calculations=[Calculation.model_validate({k:v for k,v in item.model_dump().items() if k!="requirement_id"}) for item in draft.calculations]
    result=verify_mechanical(task,draft,[ev],calculations)
    assert result.status.value == "pass"
    assert result.claim_results[0].supported is True


@pytest.mark.anyio
async def test_semantic_verifier_projection_does_not_send_source_identity():
    from datetime import UTC,datetime
    from v2.contracts import EvidenceEnvelope,DraftReport
    stub=StubModel([{'status':'pass','claim_results':[]}])
    verifier=ModelSemanticVerifier(stub,provider='stub',model_name='stub')
    ev=EvidenceEnvelope(evidence_id='e',capability='x',source='fixture',observed_at=datetime.now(UTC),rows=[],source_identity={'kind':'warehouse','warehouse_id':'frozen-eval','sha256':'a'*64})
    await verifier.verify(TaskSpec(goal='g',mode='quick',deliverable='d'),DraftReport(sections=['x'],claims=[]),{'e':ev})
    projected=stub.calls[0]['payload']['evidence'][0]
    assert 'source_identity' not in projected and 'a'*64 not in repr(projected)

@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.parametrize(('kind','phase'),[
    ('unknown','json_or_schema_validation'),('malformed','json_or_schema_validation'),
    ('empty','no_tool_or_empty'),('refusal','content_filter'),
])
async def test_safe_failure_taxonomy_exact_native_openai_path(anyio_backend,kind,phase):
    # Native SDK path is validated on Dime's supported asyncio runtime; Trio is upstream, not a production contract.
    assert anyio_backend == "asyncio"
    import httpx,json
    from openai import AsyncOpenAI
    from pydantic_ai import Agent,NativeOutput
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    from v2.adapters.models import ProviderStructuredModel
    from v2.contracts import VerificationReport
    sentinel='SECRET_SENTINEL_MUST_NOT_LEAK'
    def handler(request):
        if kind=='unknown':content=json.dumps({'status':'pass','extra':sentinel})
        elif kind=='malformed':content='{bad '+sentinel
        elif kind=='empty':content=''
        elif kind=='refusal':
            return httpx.Response(200,json={'id':'x','object':'chat.completion','created':0,'model':'fake','choices':[{'index':0,'message':{'role':'assistant','content':None,'refusal':sentinel},'finish_reason':'stop'}]})
        return httpx.Response(200,json={'id':'x','object':'chat.completion','created':0,'model':'fake','choices':[{'index':0,'message':{'role':'assistant','content':content},'finish_reason':'stop'}]})
    client=AsyncOpenAI(api_key='fake',base_url='https://fake.invalid/v1',http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),max_retries=0)
    model=OpenAIChatModel('fake',provider=OpenAIProvider(openai_client=client))
    try:
        with pytest.raises(Exception) as caught:
            await Agent(model,output_type=NativeOutput(VerificationReport,strict=True),retries=0).run('bounded')
        safe=ProviderStructuredModel._safe_failure_taxonomy(caught.value,schema=VerificationReport,route='semantic_verifier')
    finally: await client.close()
    assert safe['failure_phase']==phase
    assert safe['failure_route']=='semantic_verifier'
    assert len(safe['failure_schema_sha256'])==64
    assert sentinel not in json.dumps(safe)
    assert set(safe)=={'failure_top_class','failure_class_chain','failure_phase','failure_validation_errors','failure_validation_subtype','failure_schema_sha256','failure_route'}


def test_safe_failure_taxonomy_nested_exception_group_redacts_messages():
    import json
    from pydantic import ValidationError
    from v2.adapters.models import ProviderStructuredModel
    from v2.contracts import VerificationReport
    sentinel='SECRET_SENTINEL_MUST_NOT_LEAK'
    validation=None
    try: VerificationReport.model_validate({'status':'pass','extra':sentinel})
    except ValidationError as exc: validation=exc
    assert validation is not None
    grouped=ExceptionGroup(sentinel,[RuntimeError(sentinel),validation])
    safe=ProviderStructuredModel._safe_failure_taxonomy(grouped,schema=VerificationReport,route='semantic_verifier')
    assert safe['failure_phase']=='json_or_schema_validation'
    assert {'ExceptionGroup','RuntimeError','ValidationError'} <= set(safe['failure_class_chain'])
    assert sentinel not in json.dumps(safe)
    assert safe['failure_validation_errors']==[{'type':'extra_forbidden','loc':['<unknown-field>']}]

@pytest.mark.parametrize(('exc','phase'),[
    (__import__('openai').APITimeoutError(__import__('httpx').Request('GET','https://test.invalid')),'timeout'),
    (__import__('openai').APIConnectionError(request=__import__('httpx').Request('GET','https://test.invalid')),'transport'),
    (__import__('openai').RateLimitError('limited',response=__import__('httpx').Response(429,request=__import__('httpx').Request('GET','https://test.invalid')),body=None),'http'),
])
def test_safe_failure_taxonomy_sdk_exception_parity(exc,phase):
    from v2.adapters.models import ProviderStructuredModel
    from v2.contracts import VerificationReport
    safe=ProviderStructuredModel._safe_failure_taxonomy(exc,schema=VerificationReport,route='semantic_verifier')
    assert safe['failure_phase']==phase


def test_safe_failure_taxonomy_unknown_location_keys_are_constant_redacted():
    import json
    from pydantic import ValidationError
    from v2.adapters.models import ProviderStructuredModel
    from v2.contracts import VerificationReport
    sentinel='SECRET_SENTINEL_MUST_NOT_LEAK'
    try: VerificationReport.model_validate({'status':'partial',sentinel:{sentinel:sentinel}})
    except ValidationError as exc: validation=exc
    safe=ProviderStructuredModel._safe_failure_taxonomy(validation,schema=VerificationReport,route='semantic_verifier')
    assert sentinel not in json.dumps(safe)
    assert safe['failure_validation_errors']==[{'type':'extra_forbidden','loc':['<unknown-field>']}]


def test_safe_failure_taxonomy_redacts_dynamic_exception_class_name_and_error_type():
    import json
    from pydantic_core import PydanticCustomError
    from v2.adapters.models import ProviderStructuredModel,_safe_pydantic_error_type
    from v2.contracts import VerificationReport
    sentinel='SECRET_SENTINEL_MUST_NOT_LEAK'
    Dynamic=type(sentinel,(RuntimeError,),{})
    grouped=ExceptionGroup('bounded',[Dynamic('bounded')])
    safe=ProviderStructuredModel._safe_failure_taxonomy(grouped,schema=VerificationReport,route='semantic_verifier')
    assert safe['failure_class_chain']==['ExceptionGroup','<unknown-exception>']
    assert sentinel not in json.dumps(safe)
    assert _safe_pydantic_error_type(sentinel)=='<unknown-error-type>'

@pytest.mark.parametrize(('inner','phase'),[
    (__import__('openai').APITimeoutError(__import__('httpx').Request('GET','https://test.invalid')),'timeout'),
    (__import__('openai').APIConnectionError(request=__import__('httpx').Request('GET','https://test.invalid')),'transport'),
    (__import__('openai').RateLimitError('limited',response=__import__('httpx').Response(429,request=__import__('httpx').Request('GET','https://test.invalid')),body=None),'http'),
    (__import__('pydantic_ai.exceptions',fromlist=['ModelHTTPError']).ModelHTTPError(503,'mercury'),'http'),
])
def test_safe_failure_taxonomy_wrapped_sdk_exception_parity(inner,phase):
    from pydantic_ai.exceptions import UnexpectedModelBehavior
    from v2.adapters.models import ProviderStructuredModel
    from v2.contracts import VerificationReport
    wrapped=None
    try: raise inner
    except Exception as cause:
        try: raise UnexpectedModelBehavior('bounded') from cause
        except UnexpectedModelBehavior as exc: wrapped=exc
    assert wrapped is not None
    safe=ProviderStructuredModel._safe_failure_taxonomy(wrapped,schema=VerificationReport,route='semantic_verifier')
    assert safe['failure_phase']==phase

@pytest.mark.anyio
async def test_actual_attempt_redacts_dynamic_exception_type_and_ledger_serializes(monkeypatch):
    import json
    from v2.adapters.models import ProviderStructuredModel
    from v2.contracts import TaskSpec
    from v2.runtime import RequestEnvelope,RunLedger
    from v2.adapters import RecordedStructuredModel
    sentinel='SECRET_SENTINEL_MUST_NOT_LEAK';Dynamic=type(sentinel,(RuntimeError,),{})
    class A:
        def __init__(self,*a,**k):pass
        async def run(self,*a,**k):raise Dynamic('bounded')
    class M:model_name='mercury-2.5'
    monkeypatch.setattr('v2.adapters.models.Agent',A)
    m=ProviderStructuredModel('inception','mercury-2.5');monkeypatch.setattr(m,'_models',lambda:[('inception',M())])
    e=RequestEnvelope.freeze(provider='inception',model='mercury-2.5',route='semantic_verifier',prompt='p',context={},tool_schemas={},planner_version='v2');ledger=RunLedger('run');recorded=RecordedStructuredModel(m,ledger,turn_id='run')
    with pytest.raises(RuntimeError):await recorded.generate(schema=TaskSpec,prompt='p',payload={},envelope=e)
    encoded=json.dumps([x.model_dump(mode='json') for x in ledger.entries])
    assert sentinel not in encoded
    attempt=ledger.entries[-1].data['provider_attempts'][0]
    assert attempt['exception_type']=='<unknown-exception>' and attempt['failure_top_class']=='<unknown-exception>'


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
@pytest.mark.parametrize(('content','subtype'),[
    ({'status':'repair','claim_results':[{'claim_index':0,'supported':False}]},'unsupported_claim_missing_reason'),
    ({'status':'pass','claim_results':[{'claim_index':0,'supported':True,'reasons':['bounded']}]},'supported_claim_has_reasons'),
    ({'status':'pass','repair_instructions':['bounded']},'pass_with_findings'),
    ({'status':'repair','claim_results':[{'claim_index':0,'supported':True}]},'repair_without_findings'),
    ({'status':'partial','claim_results':[{'claim_index':0,'supported':True},{'claim_index':0,'supported':True}]},'duplicate_claim_index'),
    ({'status':'partial','missing_branches':['bounded','bounded']},'duplicate_or_empty_finding'),
])
async def test_safe_failure_validation_subtype_exact_native_openai_path(anyio_backend,content,subtype):
    # Native SDK path is validated on Dime's supported asyncio runtime; Trio is upstream, not a production contract.
    assert anyio_backend == "asyncio"
    import httpx,json
    from openai import AsyncOpenAI
    from pydantic_ai import Agent,NativeOutput
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    from v2.adapters.models import ProviderStructuredModel
    from v2.contracts import VerificationReport
    sentinel='SECRET_SENTINEL_MUST_NOT_LEAK'
    def handler(request):
        body=json.dumps(content).replace('bounded',sentinel)
        return httpx.Response(200,json={'id':'x','object':'chat.completion','created':0,'model':'fake','choices':[{'index':0,'message':{'role':'assistant','content':body},'finish_reason':'stop'}]})
    client=AsyncOpenAI(api_key='fake',base_url='https://fake.invalid/v1',http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),max_retries=0)
    model=OpenAIChatModel('fake',provider=OpenAIProvider(openai_client=client))
    try:
        with pytest.raises(Exception) as caught:
            await Agent(model,output_type=NativeOutput(VerificationReport,strict=True),retries=0).run('bounded')
        safe=ProviderStructuredModel._safe_failure_taxonomy(caught.value,schema=VerificationReport,route='semantic_verifier')
    finally: await client.close()
    assert safe['failure_validation_subtype']==subtype
    assert sentinel not in json.dumps(safe)


def test_safe_failure_validation_subtype_nested_and_dynamic_fallback():
    import json
    from pydantic import ValidationError
    from pydantic_core import PydanticCustomError
    from v2.adapters.models import ProviderStructuredModel
    from v2.contracts import VerificationReport
    sentinel='SECRET_SENTINEL_MUST_NOT_LEAK'
    try: VerificationReport.model_validate({'status':'repair','claim_results':[{'claim_index':0,'supported':False}]})
    except ValidationError as exc: known=exc
    dynamic=ValidationError.from_exception_data('x',[{'type':PydanticCustomError(sentinel,sentinel),'loc':('claim_results',0),'input':sentinel}])
    safe=ProviderStructuredModel._safe_failure_taxonomy(ExceptionGroup(sentinel,[RuntimeError(sentinel),known]),schema=VerificationReport,route='semantic_verifier')
    assert safe['failure_validation_subtype']=='unsupported_claim_missing_reason'
    assert sentinel not in json.dumps(safe)
    fallback=ProviderStructuredModel._safe_failure_taxonomy(ExceptionGroup('bounded',[dynamic]),schema=VerificationReport,route='semantic_verifier')
    assert fallback['failure_validation_subtype']=='other_contract_invariant'
    assert sentinel not in json.dumps(fallback)


@pytest.mark.parametrize(('errors','expected'),[
    (['known','dynamic'],'other_contract_invariant'),
    (['known','generic'],'other_contract_invariant'),
    (['known','different_known'],'other_contract_invariant'),
    (['known','known'],'unsupported_claim_missing_reason'),
])
def test_safe_failure_validation_subtype_conservative_mixed_groups(errors,expected):
    import json
    from pydantic import ValidationError
    from pydantic_core import PydanticCustomError
    from v2.adapters.models import ProviderStructuredModel
    from v2.contracts import VerificationReport
    sentinel='SECRET_SENTINEL_MUST_NOT_LEAK'
    def make(kind):
        if kind=='known':
            try: VerificationReport.model_validate({'status':'repair','claim_results':[{'claim_index':0,'supported':False}]})
            except ValidationError as exc: return exc
        if kind=='different_known':
            try: VerificationReport.model_validate({'status':'pass','claim_results':[{'claim_index':0,'supported':True,'reasons':['bounded']}]})
            except ValidationError as exc: return exc
        if kind=='generic':
            return ValidationError.from_exception_data('x',[{'type':'value_error','loc':('claim_results',0),'input':'bounded','ctx':{'error':ValueError('bounded')}}])
        return ValidationError.from_exception_data('x',[{'type':PydanticCustomError(sentinel,sentinel),'loc':('claim_results',0),'input':sentinel}])
    grouped=ExceptionGroup('bounded',[make(kind) for kind in errors])
    safe=ProviderStructuredModel._safe_failure_taxonomy(grouped,schema=VerificationReport,route='semantic_verifier')
    assert safe['failure_validation_subtype']==expected
    assert sentinel not in json.dumps(safe)


@pytest.mark.parametrize(('exc','phase'),[
    (__import__('openai').APITimeoutError(__import__('httpx').Request('GET','https://test.invalid')),'timeout'),
    (__import__('openai').APIConnectionError(request=__import__('httpx').Request('GET','https://test.invalid')),'transport'),
    (__import__('pydantic_ai.exceptions',fromlist=['ModelHTTPError']).ModelHTTPError(503,'bounded'),'http'),
    (__import__('pydantic_ai.exceptions',fromlist=['ContentFilterError']).ContentFilterError('bounded'),'content_filter'),
    (__import__('pydantic_ai.exceptions',fromlist=['UnexpectedModelBehavior']).UnexpectedModelBehavior('bounded'),'no_tool_or_empty'),
])
def test_safe_failure_validation_subtype_not_applicable_outside_validation(exc,phase):
    from v2.adapters.models import ProviderStructuredModel
    from v2.contracts import VerificationReport
    safe=ProviderStructuredModel._safe_failure_taxonomy(exc,schema=VerificationReport,route='semantic_verifier')
    assert safe['failure_phase']==phase
    assert safe['failure_validation_errors']==[]
    assert safe['failure_validation_subtype']=='not_applicable'


def test_safe_failure_validation_subtype_validation_phase_without_recoverable_error_is_other():
    from pydantic_ai.exceptions import UnexpectedModelBehavior
    from v2.adapters.models import ProviderStructuredModel
    from v2.contracts import VerificationReport
    validation_marker=type('ValidationError',(RuntimeError,),{})('bounded')
    try: raise validation_marker
    except Exception as cause:
        try: raise UnexpectedModelBehavior('bounded') from cause
        except UnexpectedModelBehavior as exc: wrapped=exc
    safe=ProviderStructuredModel._safe_failure_taxonomy(wrapped,schema=VerificationReport,route='semantic_verifier')
    assert safe['failure_phase']=='json_or_schema_validation'
    assert safe['failure_validation_errors']==[]
    assert safe['failure_validation_subtype']=='other_contract_invariant'


@pytest.mark.anyio
async def test_semantic_verifier_prompt_exposes_claim_result_alignment():
    from v2.contracts import DraftReport
    stub=StubModel([{'status':'pass','claim_results':[{'claim_index':0,'supported':True,'reasons':[]}]}])
    verifier=ModelSemanticVerifier(stub,provider='stub',model_name='stub')
    task=TaskSpec(goal='g',mode='quick',deliverable='d')
    draft=DraftReport(sections=['x'],claims=[{'text':'x','kind':'observed','evidence_ids':['e']}])
    evidence=EvidenceEnvelope(evidence_id='e',capability='x',source='fixture',observed_at=datetime.now(UTC),rows=[{'x':1}])
    report=await verifier.verify(task,draft,{'e':evidence})
    assert report.claim_results[0].supported is True and report.claim_results[0].reasons==[]
    prompt=stub.calls[0]['prompt']
    assert '`supported: true` requires exactly `reasons: []`' in prompt
    assert '`supported: false` requires at least one rejection reason' in prompt



def test_intake_admission_rejects_replay_omission_and_length_correct_wrong_text():
    from v2.contracts import (AdmissionBinding, IntakeAdmissionReview,
        SourceLocator, TaskSpec)
    task=TaskSpec(goal="LeBron",mode="quick",deliverable="answer",
        entities=[{"id":"2544","type":"player","display_name":"LeBron James"}])
    request="Ask LeBron James."
    target=ModelIntake._review_target(request,(),task)
    subjects=ModelIntake._expected_admission_subjects(task)
    valid=IntakeAdmissionReview(target=target,decision="admit",
        expected_subjects=subjects,bindings=[
            AdmissionBinding(subject=subjects[0], locator=SourceLocator(
                source="request",start=0,end=len(request),text=request)),
            AdmissionBinding(subject=subjects[1], locator=SourceLocator(
                source="request",start=4,end=16,text="LeBron James"))])
    assert ModelIntake._validate_review(valid,request,(),task)==[]
    replay=valid.model_copy(update={"target":target.model_copy(update={"task_sha256":"d"*64})})
    assert any("target does not match" in item for item in ModelIntake._validate_review(replay,request,(),task))
    omitted=valid.model_copy(update={"expected_subjects":(),"bindings":()})
    assert any("expected subjects" in item for item in ModelIntake._validate_review(omitted,request,(),task))
    wrong=valid.model_copy(update={"bindings": (
        valid.bindings[0], AdmissionBinding(subject=subjects[1],
        locator=SourceLocator(source="request",start=4,end=16,text="Another Name")))})
    assert any("frozen source" in item for item in ModelIntake._validate_review(wrong,request,(),task))


def test_intake_admission_context_digest_binds_role_order_and_exact_unicode_text():
    from v2.contracts import ConversationTurn, TaskSpec
    task=TaskSpec(goal="impact",mode="quick",deliverable="answer")
    a=(ConversationTurn(role="user",content="Nikola Jokić?"),
       ConversationTurn(role="assistant",content="Denver’s center."))
    b=tuple(reversed(a))
    c=(ConversationTurn(role="assistant",content="Nikola Jokić?"),
       ConversationTurn(role="user",content="Denver’s center."))
    assert ModelIntake._review_target("x",a,task).context_sha256 != ModelIntake._review_target("x",b,task).context_sha256
    assert ModelIntake._review_target("x",a,task).context_sha256 != ModelIntake._review_target("x",c,task).context_sha256


def test_intake_admission_manifest_covers_zero_entity_task_metrics_outputs_and_calculations():
    task=TaskSpec(goal="calculate pace change",mode="quick",deliverable="delta",
        metric_ids=["PACE"],requested_outputs=["PACE_DELTA"],
        calculation_requirements=[{"id":"pace_delta","description":"pace change",
            "metric_ids":["PACE"],"requested_outputs":["PACE_DELTA"]}])
    subjects=ModelIntake._expected_admission_subjects(task)
    dumped=[item.model_dump(mode="json") for item in subjects]
    assert dumped[0]=={"kind":"task","task_id":"request"}
    assert {item.get("metric_id") for item in dumped if item["kind"]=="metric"}=={"PACE"}
    assert {(item.get("owner_kind"),item.get("requirement_id"),item.get("output_id")) for item in dumped
            if item["kind"]=="output"}=={("task","request","PACE_DELTA"),("calculation","pace_delta","PACE_DELTA")}
    assert any(item.get("requirement_id")=="pace_delta" for item in dumped)


def test_block_clears_every_action_driving_task_field_before_skill_activation():
    from datetime import date
    from v2.contracts import (AdmissionFinding, IntakeAdmissionReview,
                              TaskAdmissionSubject)
    task=TaskSpec(goal="x",mode="quick",deliverable="x",season={"value":"2025-26","source":"user","confidence":1.0},
        as_of=date(2026,1,1),subquestions=["q"],required_evidence=["standings"],
        assumptions=["a"],skills=["trade-analysis"],metric_ids=["PACE"],requested_outputs=["PACE"])
    subject=TaskAdmissionSubject(kind="task")
    review=IntakeAdmissionReview(target=ModelIntake._review_target("x",(),task),decision="block",
        expected_subjects=ModelIntake._expected_admission_subjects(task),findings=[AdmissionFinding(
            code="subject_mismatch",affected_subjects=[subject])])
    blocked=ModelIntake._apply_review(review,"x",(),task)
    assert blocked.season is None and blocked.as_of is None
    assert blocked.subquestions==[] and blocked.assumptions==[] and blocked.skills==[]
    assert blocked.required_evidence==[] and blocked.metric_ids==[] and blocked.requested_outputs==[]


def test_admission_dimension_ids_reject_noncanonical_values_at_task_boundary():
    from pydantic import ValidationError
    for value in ("!!!", "A B", "ÉFG", "lower"):
        with pytest.raises(ValidationError):
            TaskSpec(goal="x",mode="quick",deliverable="x",metric_ids=[value])
        with pytest.raises(ValidationError):
            TaskSpec(goal="x",mode="quick",deliverable="x",requested_outputs=[value])


def test_admission_manifest_preserves_same_metric_under_distinct_requirement_scopes():
    task=TaskSpec(goal="compare",mode="quick",deliverable="answer",requirements=[
        {"id":"first","description":"first","capability_options":["standings"],"metric_ids":["PACE"]},
        {"id":"second","description":"second","capability_options":["standings"],"metric_ids":["PACE"]},
    ])
    metrics=[item.model_dump(mode="json") for item in ModelIntake._expected_admission_subjects(task)
             if item.kind=="metric"]
    assert metrics==[
        {"kind":"metric","owner_kind":"evidence","owner_id":"first","metric_id":"PACE"},
        {"kind":"metric","owner_kind":"evidence","owner_id":"second","metric_id":"PACE"},
    ]


def test_evidence_and_calculation_requirement_ids_cannot_collide():
    from pydantic import ValidationError
    with pytest.raises(ValidationError,match="ids overlap"):
        TaskSpec(goal="x",mode="quick",deliverable="x",
            requirements=[{"id":"same","description":"e","capability_options":["standings"]}],
            calculation_requirements=[{"id":"same","description":"c"}])


class StagedAdmissionModel:
    def __init__(self, intake, requirement_review, admission_factory):
        self.intake=intake;self.requirement_review=requirement_review
        self.admission_factory=admission_factory;self.calls=[]
    async def generate(self,**call):
        self.calls.append(call);route=call["envelope"].route
        value=(self.intake if route=="intake" else self.requirement_review
               if route=="requirement_review" else self.admission_factory(call["payload"])
               if route=="intake_admission" else None)
        if value is None:raise AssertionError(route)
        return fixture_result(call,value)


def _staged_admission(payload, spans, *, decision="admit", block_index=0):
    if decision=="block": return blocked_subject(payload,block_index)
    return admitted(payload,spans)


@pytest.mark.anyio
async def test_final_admission_blocks_requirement_review_metric_substitution_before_planning():
    intake={"goal":"LeBron points","mode":"quick","deliverable":"points",
            "entities":[{"id":"2544","type":"player","display_name":"LeBron James"}]}
    wrong={"requirements":[{"id":"scoring","description":"wrong assists",
        "capability_options":["standings"],"metric_ids":["AST"],"requested_outputs":["AST"]}]}
    model=StagedAdmissionModel(intake,wrong,lambda payload:blocked_subject(payload,3))
    task=await ModelIntake(model,**stage_kwargs(),intake_admission=True,
                          requirement_review=True).understand("Show LeBron James PTS.")
    assert task.requirements==[] and task.metric_ids==[] and task.skills==[]
    assert [call["envelope"].route for call in model.calls]==[
        "intake","requirement_review","intake_admission"]


@pytest.mark.anyio
async def test_final_admission_binds_post_review_evidence_and_calculation_scopes():
    request="Show LeBron James PTS and PTS change."
    intake={"goal":"LeBron scoring","mode":"quick","deliverable":"points change",
            "entities":[{"id":"2544","type":"player","display_name":"LeBron James"}]}
    reviewed={"requirements":[{"id":"scoring","description":"points",
        "capability_options":["standings"],"metric_ids":["PTS"],"requested_outputs":["PTS"]}],
        "calculation_requirements":[{"id":"change","description":"change",
        "metric_ids":["PTS"],"requested_outputs":["PTS_DELTA"]}]}
    def approve(payload):
        spans=[]
        for item in payload["expected_subjects"]:
            if item["kind"]=="entity":text="LeBron James"
            elif item["kind"]=="metric":text="PTS"
            elif item["kind"]=="output" and item["output_id"]=="PTS_DELTA":text="PTS change"
            elif item["kind"]=="output":text="PTS"
            elif item["kind"]=="requirement" and item["requirement_kind"]=="calculation":text="change"
            elif item["kind"]=="requirement":text="PTS"
            else:text=request
            spans.append(("request",None,text))
        return admitted(payload,spans)
    model=StagedAdmissionModel(intake,reviewed,approve)
    task=await ModelIntake(model,**stage_kwargs(),intake_admission=True,
                          requirement_review=True).understand(request)
    assert task.requirements[0].metric_ids==["PTS"]
    assert task.calculation_requirements[0].requested_outputs==["PTS_DELTA"]
    admission_call=model.calls[-1]
    assert admission_call["envelope"].route=="intake_admission"
    assert admission_call["payload"]["target"]["task_sha256"]==ModelIntake._review_target(request,(),task).task_sha256


# ---------------------------------------------------------------------------
# Ranked team ratings: typed enums, deterministic verifier, no text inference.
# ---------------------------------------------------------------------------

def _typed_catalog():
    from v2.runtime.assembly import capability_catalog
    return capability_catalog()

def _typed_ranked_task(metric="DEF_RATING", direction="asc", team="", season="2025-26"):
    from v2.arguments import CapabilityArgumentSet, RequirementArguments, encode_argument
    from v2.contracts import EvidenceRequirement
    args = {"requested_metric": metric, "ranking_direction": direction,
            "team": team, "season": season}
    req = EvidenceRequirement(
        id="rank", description="ranked team ratings",
        capability_options=["team_ratings"],
        capability_argument_sets=[CapabilityArgumentSet(
            capability_id="team_ratings",
            arguments=RequirementArguments.model_validate(
                {"entries": [encode_argument(k, v) for k, v in args.items()]}))])
    return TaskSpec(goal="rank", mode="quick", deliverable="team",
                    season={"value": season, "source": "user", "confidence": 1},
                    required_evidence=["team_ratings"], requirements=[req])

def _ranked_wire_entries(arguments):
    return {"requirements": [{
        "id": "rank", "description": "ranked team ratings",
        "capability_options": ["team_ratings"],
        "capability_argument_sets": [{
            "capability_id": "team_ratings",
            "arguments": {"entries": [
                StubModel._wire_entry(k, v) for k, v in arguments.items()]}}],
        "metric_ids": None, "requested_outputs": None}],
        "calculation_requirements": None,
        "missing_subquestions": None, "missing_skills": None}

def _review_intake(arguments):
    return ModelIntake(StubModel([]), provider="stub", model_name="stub",
                       capability_catalog=_typed_catalog())

@pytest.mark.anyio
async def test_ranked_verifier_rejects_invalid_metric_enum():
    intake = _review_intake(None)
    wire = RequirementReviewWire.model_validate(_ranked_wire_entries(
        {"requested_metric": "DEFENSE", "ranking_direction": "asc",
         "team": "", "season": "2025-26"}))
    with pytest.raises(ValueError, match="is not one of"):
        intake._validate_requirement_wire(wire)

@pytest.mark.anyio
async def test_ranked_verifier_rejects_invalid_direction_enum():
    intake = _review_intake(None)
    wire = RequirementReviewWire.model_validate(_ranked_wire_entries(
        {"requested_metric": "DEF_RATING", "ranking_direction": "up",
         "team": "", "season": "2025-26"}))
    with pytest.raises(ValueError, match="is not one of"):
        intake._validate_requirement_wire(wire)

@pytest.mark.anyio
async def test_ranked_verifier_rejects_missing_direction():
    intake = _review_intake(None)
    wire = RequirementReviewWire.model_validate(_ranked_wire_entries(
        {"requested_metric": "DEF_RATING", "ranking_direction": "",
         "team": "", "season": "2025-26"}))
    with pytest.raises(ValueError, match="RANKED_DIRECTION_UNSPECIFIED"):
        intake._validate_requirement_wire(wire)

@pytest.mark.anyio
async def test_ranked_verifier_rejects_direction_without_metric():
    intake = _review_intake(None)
    wire = RequirementReviewWire.model_validate(_ranked_wire_entries(
        {"requested_metric": "", "ranking_direction": "asc",
         "team": "", "season": "2025-26"}))
    with pytest.raises(ValueError, match="RANKED_ARGUMENT_CONFLICT"):
        intake._validate_requirement_wire(wire)

@pytest.mark.anyio
async def test_ranked_verifier_allows_named_team_without_direction():
    intake = _review_intake(None)
    wire = RequirementReviewWire.model_validate(_ranked_wire_entries(
        {"requested_metric": "DEF_RATING", "ranking_direction": "",
         "team": "Celtics", "season": "2025-26"}))
    intake._validate_requirement_wire(wire)

@pytest.mark.anyio
async def test_ranked_null_direction_drop_then_deterministic_rejection():
    from v2.adapters.models import provider_to_source
    intake = _review_intake(None)
    drops = []
    schema = intake._review_argument_schema("team_ratings")
    wire = RequirementReviewWire.model_validate(_ranked_wire_entries(
        {"requested_metric": "DEF_RATING", "ranking_direction": None,
         "team": "", "season": "2025-26"}))
    option = wire.requirements[0].capability_argument_sets[0]
    arguments = dict(provider_to_source(option.arguments, "requirement",
        route="requirement_review", capability_id="team_ratings",
        argument_schema=schema, drops=drops))
    assert arguments.get("ranking_direction", "") == ""
    assert any(d["key"] == "ranking_direction" for d in drops)
    with pytest.raises(ValueError, match="RANKED_DIRECTION_UNSPECIFIED"):
        intake._validate_requirement_wire(wire)

@pytest.mark.anyio
async def test_ranked_intake_review_conflict_is_typed_gap():
    intake = _review_intake(None)
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    review = RequirementReview.model_validate({"requirements": [{
        "id": "rank", "description": "ranked team ratings",
        "capability_options": ["team_ratings"],
        "capability_arguments": {"requested_metric": "OFF_RATING",
                                 "ranking_direction": "desc",
                                 "team": "", "season": "2025-26"}}]})
    reconciled, carried, conflicts = intake._reconcile_typed_ranked_arguments(task, review)
    assert reconciled.requirements == []
    assert carried == []
    assert reconciled.missing_subquestions == []
    assert conflicts == [
        {"route": "requirement_review", "capability_id": "team_ratings",
         "key": "requested_metric", "rule": "ranked-argument-conflict"},
        {"route": "requirement_review", "capability_id": "team_ratings",
         "key": "ranking_direction", "rule": "ranked-argument-conflict"}]

@pytest.mark.anyio
async def test_ranked_conflict_stays_out_of_subquestions_reaches_ledger_and_gaps():
    from v2.adapters.models import RecordedStructuredModel, _deterministic_rank_draft
    from v2.runtime.ledger import RunLedger
    model = StubModel([{
        "requirements": [{
            "id": "rank", "description": "ranked team ratings",
            "capability_options": ["team_ratings"],
            "capability_argument_sets": [{
                "capability_id": "team_ratings",
                "arguments": {"requested_metric": "OFF_RATING",
                              "ranking_direction": "asc", "team": "",
                              "season": "2025-26"}}],
            "metric_ids": None, "requested_outputs": None}],
        "calculation_requirements": None,
        "missing_subquestions": None, "missing_skills": None}])
    ledger = RunLedger("run")
    recorded = RecordedStructuredModel(model, ledger, turn_id="t")
    intake = ModelIntake(recorded, provider="stub", model_name="stub",
                         capability_catalog=_typed_catalog())
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    review = await intake._review_requirements("who has the best defense", task)
    assert review.requirements == []
    assert review.missing_subquestions == []
    attempts = [entry for entry in ledger.entries
                if entry.kind == "assistant/attempt"]
    assert len(attempts) == 1
    assert attempts[0].data["ranked_argument_conflicts"] == [
        {"route": "requirement_review", "capability_id": "team_ratings",
         "key": "requested_metric", "rule": "ranked-argument-conflict"}]
    assert "carried_from_intake" not in attempts[0].data
    draft = _deterministic_rank_draft(
        task.model_copy(update={"requirements": review.requirements}), [])
    assert draft is not None
    assert draft.claims == []
    assert draft.gaps == [
        "Ranked team ratings could not be published: intake required "
        "team_ratings evidence but no requirement carries typed "
        "ranking arguments."]

@pytest.mark.anyio
async def test_ranked_conflict_with_empty_direction_fails_closed_at_wire_validation():
    from v2.adapters.models import RecordedStructuredModel
    from v2.runtime.ledger import RunLedger
    model = StubModel([{
        "requirements": [{
            "id": "rank", "description": "ranked team ratings",
            "capability_options": ["team_ratings"],
            "capability_argument_sets": [{
                "capability_id": "team_ratings",
                "arguments": {"requested_metric": "OFF_RATING",
                              "ranking_direction": "", "team": "",
                              "season": "2025-26"}}],
            "metric_ids": None, "requested_outputs": None}],
        "calculation_requirements": None,
        "missing_subquestions": None, "missing_skills": None}])
    ledger = RunLedger("run")
    recorded = RecordedStructuredModel(model, ledger, turn_id="t")
    intake = ModelIntake(recorded, provider="stub", model_name="stub",
                         capability_catalog=_typed_catalog())
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    with pytest.raises(ValueError, match="RANKED_DIRECTION_UNSPECIFIED"):
        await intake._review_requirements("who has the best defense", task)
    attempts = [entry for entry in ledger.entries
                if entry.kind == "assistant/attempt"]
    assert len(attempts) == 1
    assert attempts[0].data["ranked_argument_conflicts"] == [
        {"route": "requirement_review", "capability_id": "team_ratings",
         "key": "requested_metric", "rule": "ranked-argument-conflict"}]
    assert "carried_from_intake" not in attempts[0].data

@pytest.mark.anyio
async def test_ranked_intake_review_season_conflict_is_typed_gap():
    intake = _review_intake(None)
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc", season="2025-26")
    review = RequirementReview.model_validate({"requirements": [{
        "id": "rank", "description": "ranked team ratings",
        "capability_options": ["team_ratings"],
        "capability_arguments": {"requested_metric": "DEF_RATING",
                                 "ranking_direction": "asc",
                                 "team": "", "season": "2024-25"}}]})
    reconciled, carried, conflicts = intake._reconcile_typed_ranked_arguments(task, review)
    assert reconciled.requirements == []
    assert carried == []
    assert reconciled.missing_subquestions == []
    assert conflicts == [
        {"route": "requirement_review", "capability_id": "team_ratings",
         "key": "season", "rule": "ranked-argument-conflict"}]

@pytest.mark.anyio
async def test_ranked_carried_from_intake_applies_and_logs_metadata():
    intake = _review_intake(None)
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    review = RequirementReview.model_validate({"requirements": [{
        "id": "rank", "description": "ranked team ratings",
        "capability_options": ["team_ratings"],
        "capability_arguments": {"requested_metric": "",
                                 "ranking_direction": "",
                                 "team": "", "season": "2025-26"}}]})
    reconciled, rows, conflicts = intake._reconcile_typed_ranked_arguments(task, review)
    assert len(reconciled.requirements) == 1
    carried = capability_arguments_for(reconciled.requirements[0], "team_ratings")
    assert carried["requested_metric"] == "DEF_RATING"
    assert carried["ranking_direction"] == "asc"
    assert {r["key"] for r in rows} == {"requested_metric", "ranking_direction"}
    assert all(r["rule"] == "carried-from-intake" and
               r["route"] == "requirement_review" and
               r["capability_id"] == "team_ratings" for r in rows)
    assert conflicts == []

@pytest.mark.anyio
async def test_ranked_carries_apply_before_wire_validation():
    intake = _review_intake(None)
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    wire = RequirementReviewWire.model_validate(_ranked_wire_entries(
        {"requested_metric": "DEF_RATING", "ranking_direction": "",
         "team": "", "season": "2025-26"}))
    with pytest.raises(ValueError, match="RANKED_DIRECTION_UNSPECIFIED"):
        intake._validate_requirement_wire(wire)
    carried = intake._apply_ranked_carries_to_wire(task, wire)
    option = carried.requirements[0].capability_argument_sets[0]
    arguments = dict(provider_to_source(
        option.arguments, "requirement",
        route="requirement_review", capability_id="team_ratings",
        argument_schema=intake._review_argument_schema("team_ratings")))
    assert arguments["requested_metric"] == "DEF_RATING"
    assert arguments["ranking_direction"] == "asc"
    intake._validate_requirement_wire(carried)

@pytest.mark.anyio
async def test_ranked_carries_do_not_apply_on_typed_conflict():
    intake = _review_intake(None)
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    wire = RequirementReviewWire.model_validate(_ranked_wire_entries(
        {"requested_metric": "OFF_RATING", "ranking_direction": "",
         "team": "", "season": "2025-26"}))
    carried = intake._apply_ranked_carries_to_wire(task, wire)
    option = carried.requirements[0].capability_argument_sets[0]
    arguments = dict(provider_to_source(
        option.arguments, "requirement",
        route="requirement_review", capability_id="team_ratings",
        argument_schema=intake._review_argument_schema("team_ratings")))
    assert arguments["requested_metric"] == "OFF_RATING"
    assert arguments["ranking_direction"] == ""

@pytest.mark.anyio
async def test_ranked_review_carries_omission_single_shot():
    model = StubModel([{
        "requirements": [{
            "id": "rank", "description": "best defense",
            "capability_options": ["team_ratings"],
            "capability_argument_sets": [{
                "capability_id": "team_ratings",
                "arguments": {"requested_metric": "DEF_RATING",
                              "ranking_direction": "", "team": "",
                              "season": "2025-26"}}],
            "metric_ids": None, "requested_outputs": None}],
        "calculation_requirements": None,
        "missing_subquestions": None, "missing_skills": None}])
    intake = ModelIntake(model, provider="stub", model_name="stub",
                         capability_catalog=_typed_catalog())
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    review = await intake._review_requirements("who has the best defense", task)
    assert len(model.calls) == 1
    arguments = capability_arguments_for(review.requirements[0], "team_ratings")
    assert arguments["requested_metric"] == "DEF_RATING"
    assert arguments["ranking_direction"] == "asc"

@pytest.mark.anyio
async def test_ranked_ledger_metadata_matches_applied_carries_end_to_end():
    from v2.adapters.models import RecordedStructuredModel
    from v2.runtime.ledger import RunLedger
    model = StubModel([{
        "requirements": [{
            "id": "rank", "description": "best defense",
            "capability_options": ["team_ratings"],
            "capability_argument_sets": [{
                "capability_id": "team_ratings",
                "arguments": {"requested_metric": "DEF_RATING",
                              "ranking_direction": "", "team": "",
                              "season": "2025-26"}}],
            "metric_ids": None, "requested_outputs": None}],
        "calculation_requirements": None,
        "missing_subquestions": None, "missing_skills": None}])
    ledger = RunLedger("run")
    recorded = RecordedStructuredModel(model, ledger, turn_id="t")
    intake = ModelIntake(recorded, provider="stub", model_name="stub",
                         capability_catalog=_typed_catalog())
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    review = await intake._review_requirements("who has the best defense", task)
    applied = capability_arguments_for(review.requirements[0], "team_ratings")
    assert applied["ranking_direction"] == "asc"
    attempts = [entry for entry in ledger.entries
                if entry.kind == "assistant/attempt"]
    assert len(attempts) == 1
    assert attempts[0].data["carried_from_intake"] == [
        {"route": "requirement_review", "capability_id": "team_ratings",
         "key": "ranking_direction", "rule": "carried-from-intake"}]

@pytest.mark.anyio
async def test_ranked_prose_does_not_change_reconciliation():
    intake = _review_intake(None)
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    reviews = []
    for description in ("lowest defensive rating!!! which team is the best?!",
                        "ranked team ratings"):
        reviews.append(RequirementReview.model_validate({"requirements": [{
            "id": "rank", "description": description,
            "capability_options": ["team_ratings"],
            "capability_arguments": {"requested_metric": "DEF_RATING",
                                     "ranking_direction": "asc",
                                     "team": "", "season": "2025-26"}}]}))
    first, first_rows, first_conflicts = intake._reconcile_typed_ranked_arguments(task, reviews[0])
    second, second_rows, second_conflicts = intake._reconcile_typed_ranked_arguments(task, reviews[1])
    assert first_rows == second_rows
    assert first_conflicts == second_conflicts == []
    assert (capability_arguments_for(first.requirements[0], "team_ratings")
            == capability_arguments_for(second.requirements[0], "team_ratings"))

@pytest.mark.anyio
async def test_review_outage_with_typed_intake_carries_typed_arguments():
    class ReviewDown:
        async def generate(self, **call):
            raise RuntimeError("all structured-output providers failed [x]")
    intake = ModelIntake(ReviewDown(), provider="stub", model_name="stub",
                         capability_catalog=_typed_catalog())
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    review = await intake._review_requirements("best defense", task)
    assert len(review.requirements) == 1
    arguments = capability_arguments_for(review.requirements[0], "team_ratings")
    assert arguments["requested_metric"] == "DEF_RATING"
    assert arguments["ranking_direction"] == "asc"
    assert arguments["season"] == "2025-26"
    assert review.missing_subquestions == []

@pytest.mark.anyio
async def test_review_outage_without_typed_intake_leaves_gap_not_inference():
    from v2.adapters.models import _deterministic_rank_draft
    class ReviewDown:
        async def generate(self, **call):
            raise RuntimeError("all structured-output providers failed [x]")
    intake = ModelIntake(ReviewDown(), provider="stub", model_name="stub",
                         capability_catalog=_typed_catalog())
    task = TaskSpec(goal="rank", mode="quick", deliverable="team",
                    season={"value": "2025-26", "source": "user", "confidence": 1},
                    required_evidence=["team_ratings"], requirements=[])
    review = await intake._review_requirements("best defense", task)
    assert len(review.requirements) == 1
    arguments = capability_arguments_for(review.requirements[0], "team_ratings")
    assert "requested_metric" not in arguments
    assert arguments["season"] == "2025-26"
    assert review.missing_subquestions == []
    draft = _deterministic_rank_draft(task.model_copy(update={
        "requirements": review.requirements}), [])
    assert draft is not None
    assert draft.claims == []
    assert draft.gaps == [
        "Ranked team ratings could not be published: intake required "
        "team_ratings evidence but no requirement carries typed "
        "ranking arguments."]

def test_ranked_verifier_needs_no_provider():
    class ExplodingModel:
        async def generate(self, **call):
            raise AssertionError("the deterministic verifier must not consult a provider")
    from v2.adapters.models import ranked_team_arguments_error
    intake = ModelIntake(ExplodingModel(), provider="stub", model_name="stub",
                         capability_catalog=_typed_catalog())
    assert ranked_team_arguments_error("team_ratings", {
        "requested_metric": "DEF_RATING", "ranking_direction": "",
        "team": "", "season": "2025-26"}) is not None
    assert ranked_team_arguments_error("team_ratings", {
        "requested_metric": "DEF_RATING", "ranking_direction": "asc",
        "team": "", "season": "2025-26"}) is None
    wire = RequirementReviewWire.model_validate(_ranked_wire_entries(
        {"requested_metric": "DEF_RATING", "ranking_direction": "asc",
         "team": "", "season": "2025-26"}))
    intake._validate_requirement_wire(wire)

def test_ranked_deterministic_draft_uses_typed_metric_ids_not_prose():
    from datetime import datetime, UTC
    from v2.adapters.models import _deterministic_rank_draft
    from v2.contracts import CalculationRequirement, EvidenceEnvelope
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    typed_calc = CalculationRequirement(
        id="calc_rank", description="which team is the best defense",
        metric_ids=["DEF_RATING"])
    prose_calc = CalculationRequirement(
        id="calc_prose",
        description="lowest defensive rating leader with the best defense numbers",
        metric_ids=[])
    task = task.model_copy(update={
        "calculation_requirements": [typed_calc, prose_calc]})
    evidence = [EvidenceEnvelope(
        evidence_id="r", capability="team_ratings", source="fixture",
        observed_at=datetime.now(UTC), season="2025-26",
        rows=[{"TEAM_NAME": "High", "DEF_RATING": 110},
              {"TEAM_NAME": "Low", "DEF_RATING": 100}],
        metric_definitions={"__requested_metric__": "DEF_RATING"})]
    draft = _deterministic_rank_draft(task, evidence)
    assert draft is not None
    assert [c.requirement_id for c in draft.calculations] == ["calc_rank"]
    assert draft.blocked_calculation_requirement_ids == ["calc_prose"]
    assert "defensive rating" in draft.claims[0].text
    assert "DEF_RATING" not in draft.claims[0].text

@pytest.mark.anyio
async def test_ranked_intake_internal_disagreement_is_typed_gap_not_override():
    from v2.arguments import CapabilityArgumentSet, RequirementArguments, encode_argument
    from v2.contracts import EvidenceRequirement
    def req(req_id, direction):
        args = {"requested_metric": "DEF_RATING", "ranking_direction": direction,
                "team": "", "season": "2025-26"}
        return EvidenceRequirement(
            id=req_id, description="ranked team ratings",
            capability_options=["team_ratings"],
            capability_argument_sets=[CapabilityArgumentSet(
                capability_id="team_ratings",
                arguments=RequirementArguments.model_validate(
                    {"entries": [encode_argument(k, v) for k, v in args.items()]}))])
    intake = _review_intake(None)
    task = TaskSpec(goal="rank", mode="quick", deliverable="team",
                    season={"value": "2025-26", "source": "user", "confidence": 1},
                    required_evidence=["team_ratings"],
                    requirements=[req("a", "asc"), req("b", "desc")])
    assert intake._intake_ranked_typed_conflicts(task) == ["ranking_direction"]
    review = RequirementReview.model_validate({"requirements": [{
        "id": "rank", "description": "ranked team ratings",
        "capability_options": ["team_ratings"],
        "capability_arguments": {"requested_metric": "DEF_RATING",
                                 "ranking_direction": "",
                                 "team": "", "season": "2025-26"}}]})
    reconciled, rows, conflicts = intake._reconcile_typed_ranked_arguments(task, review)
    assert reconciled.requirements == []
    assert rows == []
    assert reconciled.missing_subquestions == []
    assert conflicts == [
        {"route": "requirement_review", "capability_id": "team_ratings",
         "key": "ranking_direction", "rule": "ranked-argument-conflict"}]
    wire = RequirementReviewWire.model_validate(_ranked_wire_entries(
        {"requested_metric": "DEF_RATING", "ranking_direction": "",
         "team": "", "season": "2025-26"}))
    carried = intake._apply_ranked_carries_to_wire(task, wire)
    assert carried.requirements[0].capability_argument_sets[0].arguments \
        == wire.requirements[0].capability_argument_sets[0].arguments

@pytest.mark.anyio
async def test_ranked_agreement_survives_when_review_matches_intake():
    intake = _review_intake(None)
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    review = RequirementReview.model_validate({"requirements": [{
        "id": "rank", "description": "ranked team ratings",
        "capability_options": ["team_ratings"],
        "capability_arguments": {"requested_metric": "DEF_RATING",
                                 "ranking_direction": "asc",
                                 "team": "", "season": "2025-26"}}]})
    reconciled, rows, conflicts = intake._reconcile_typed_ranked_arguments(task, review)
    assert len(reconciled.requirements) == 1
    assert rows == []
    assert conflicts == []

@pytest.mark.anyio
async def test_ranked_request_text_independence():
    def review_model():
        return StubModel([{
            "requirements": [{
                "id": "rank", "description": "ranked team ratings",
                "capability_options": ["team_ratings"],
                "capability_argument_sets": [{
                    "capability_id": "team_ratings",
                    "arguments": {"requested_metric": "DEF_RATING",
                                  "ranking_direction": "asc",
                                  "team": "", "season": "2025-26"}}],
                "metric_ids": None, "requested_outputs": None}],
            "calculation_requirements": None,
            "missing_subquestions": None, "missing_skills": None}])
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    reviews = []
    for request in ("lowest defensive rating",
                    "which team defends best???! show me #1 D"):
        intake = ModelIntake(review_model(), provider="stub", model_name="stub",
                             capability_catalog=_typed_catalog())
        reviews.append(await intake._review_requirements(request, task))
    # The request text is never consulted: identical stubbed model outputs
    # give identical reviews regardless of phrasing.
    assert (reviews[0].model_dump(mode="json")
            == reviews[1].model_dump(mode="json"))
    assert capability_arguments_for(
        reviews[0].requirements[0], "team_ratings")["requested_metric"] == "DEF_RATING"

def _planner_node(node_id, capability, arguments, covers=("rank",)):
    full = {"team": "", "season": "2025-26"}
    full.update(arguments)
    return {"id": node_id, "description": "ranked team ratings",
            "capability": capability, "covers_requirement_ids": list(covers),
            "arguments": full, "depends_on": None,
            "max_attempts": None, "status": None}

@pytest.mark.anyio
async def test_planner_ranked_direction_mismatch_fails_closed():
    planner = ModelPlanner(StubModel([
        {"nodes": [_planner_node("n", "team_ratings",
                                 {"requested_metric": "OFF_RATING",
                                  "ranking_direction": "desc",
                                  "season": "2025-26"})]}]),
        provider="stub", model_name="stub", capability_catalog=_typed_catalog())
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    with pytest.raises(PlannerArgumentError, match="RANKED_ARGUMENT_CONFLICT"):
        await planner.plan(task)

@pytest.mark.anyio
async def test_planner_ranked_missing_direction_replans_then_fails_closed():
    model = StubModel([
        {"nodes": [_planner_node("n", "team_ratings",
                                 {"requested_metric": "DEF_RATING",
                                  "ranking_direction": "",
                                  "season": "2025-26"})]},
        {"nodes": [_planner_node("n", "team_ratings",
                                 {"requested_metric": "DEF_RATING",
                                  "ranking_direction": "",
                                  "season": "2025-26"})]},
    ])
    planner = ModelPlanner(model, provider="stub", model_name="stub",
                           capability_catalog=_typed_catalog())
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    with pytest.raises(PlannerArgumentError, match="RANKED_DIRECTION_UNSPECIFIED"):
        await planner.plan(task)
    assert len(model.calls) == 2
    feedback = model.calls[1]["payload"]["coverage_feedback"]
    assert feedback["missing_required_arguments"] == {"n": ["ranking_direction"]}

@pytest.mark.anyio
async def test_planner_ranked_matching_arguments_pass():
    planner = ModelPlanner(StubModel([
        {"nodes": [_planner_node("n", "team_ratings",
                                 {"requested_metric": "DEF_RATING",
                                  "ranking_direction": "asc",
                                  "season": "2025-26"})]}]),
        provider="stub", model_name="stub", capability_catalog=_typed_catalog())
    task = _typed_ranked_task(metric="DEF_RATING", direction="asc")
    plan = await planner.plan(task)
    assert plan.nodes[0].arguments["requested_metric"] == "DEF_RATING"
    assert plan.nodes[0].arguments["ranking_direction"] == "asc"

@pytest.mark.anyio
async def test_planner_ranked_invalid_metric_enum_rejected():
    planner = ModelPlanner(StubModel([
        {"nodes": [_planner_node("n", "team_ratings",
                                 {"requested_metric": "DEFENSE",
                                  "ranking_direction": "asc"})]}]),
        provider="stub", model_name="stub", capability_catalog=_typed_catalog())
    with pytest.raises(PlannerArgumentError, match="is not one of"):
        await planner.plan(_typed_ranked_task())

def test_no_ranked_text_derivation_symbols_remain():
    import ast, pathlib
    tree = ast.parse((pathlib.Path(__file__).parents[3]
                      / "v2" / "adapters" / "models.py").read_text())
    names = {node.name for node in ast.walk(tree)
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    removed = {"ranked_team_constraints", "canonical_ranking_direction",
               "canonical_team_rating_metric", "_strip_ranked_team_branches",
               "_rebuild_ranked_team_branch", "_reconcile_ranked_team_review"}
    assert not (names & removed), names & removed
    rating = (pathlib.Path(__file__).parents[3] / "app" / "tools"
              / "rating_metrics.py").read_text()
    assert "RANKING_DIRECTION_ALIASES" not in rating
    assert "RankedTeamConstraintError" not in rating

def test_ranked_metric_vocabulary_is_label_map_from_single_source():
    from app.tools.rating_metrics import RANKING_DIRECTIONS, TEAM_RATING_METRICS
    assert TEAM_RATING_METRICS == {
        "OFF_RATING": {"label": "offensive rating", "format": "general"},
        "DEF_RATING": {"label": "defensive rating", "format": "general"},
        "NET_RATING": {"label": "net rating", "format": "general"},
        "PACE": {"label": "pace", "format": "general"},
        "TS_PCT": {"label": "true shooting percentage", "format": "decimal3"},
        "TM_TOV_PCT": {"label": "turnover percentage", "format": "decimal3"},
    }
    assert tuple(RANKING_DIRECTIONS) == ("asc", "desc")
    catalog = _typed_catalog()
    props = catalog["team_ratings"]["arguments"]["properties"]
    assert props["requested_metric"]["enum"] == ["", *TEAM_RATING_METRICS]
    assert props["ranking_direction"]["enum"] == ["", *RANKING_DIRECTIONS]

def test_ranked_typed_functions_never_read_request_text_or_use_regex():
    import ast, pathlib
    root = pathlib.Path(__file__).parents[3]
    tree = ast.parse((root / "v2" / "adapters" / "models.py").read_text())
    targets = {"_intake_typed_ranked_arguments", "_intake_ranked_typed_conflicts",
               "_ranked_typed_carries", "_ranked_typed_conflicts",
               "_decode_review_ranked_arguments", "_ranked_review_typed_decisions",
               "_apply_ranked_carries_to_wire", "_reconcile_typed_ranked_arguments",
               "ranked_team_arguments_error", "_validate_requirement_wire",
               "_deterministic_rank_draft"}
    by_name = {node.name: node for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert not (targets - set(by_name)), targets - set(by_name)

    def check_ranked_function(name: str, node: ast.AST, path: str) -> None:
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute) and child.attr in {
                    "goal", "description", "request", "subquestions"}:
                raise AssertionError(f"{path}:{name} reads .{child.attr} text")
            if isinstance(child, ast.Attribute) and isinstance(
                    child.value, ast.Name) and child.value.id == "re":
                raise AssertionError(f"{path}:{name} uses the re module")
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                imported = [alias.name for alias in child.names]
                if isinstance(child, ast.ImportFrom) and child.module:
                    imported.append(child.module)
                assert "re" not in imported, f"{path}:{name} imports re"
            if isinstance(child, ast.Compare) and any(
                    isinstance(op, (ast.In, ast.NotIn)) for op in child.ops):
                for comparator in child.comparators:
                    if (isinstance(child.left, ast.Constant)
                            and isinstance(child.left.value, str)
                            and isinstance(comparator, ast.Name)):
                        raise AssertionError(
                            f"{path}:{name} does substring matching on text")

    for name in sorted(targets):
        check_ranked_function(name, by_name[name], "v2/adapters/models.py")
    league = ast.parse((root / "app" / "tools" / "league.py").read_text())
    get_ratings = next(node for node in ast.walk(league)
                       if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and node.name == "get_ratings")
    check_ranked_function("get_ratings", get_ratings, "app/tools/league.py")

def test_no_request_text_regex_routes_ranked_arguments():
    import ast, pathlib
    for rel in ("v2/adapters/models.py", "app/tools/league.py"):
        tree = ast.parse((pathlib.Path(__file__).parents[3] / rel).read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = node.name.lower()
            if "ranked" not in name and "rating" not in name:
                continue
            src = ast.get_source_segment(
                (pathlib.Path(__file__).parents[3] / rel).read_text(), node) or ""
            assert "import re" not in src and "re.compile" not in src, \
                f"{rel}:{node.name} uses regex for ranked argument routing"
