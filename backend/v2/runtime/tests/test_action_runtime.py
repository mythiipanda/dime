from __future__ import annotations

import json

import pytest

from v2.adapters.models import RecordedStructuredModel
from v2.contracts import (
    Claim, DraftReport, EntityRef, EvidenceOutputBinding, EvidenceRequirement,
    SeasonRef, TaskSpec, VerificationReport, VerificationStatus,
)
from v2.projects.service import ProjectStore
from v2.runtime import FakeCapability, PlanExecutor, Runtime
from v2.runtime.action_loop import ActionRuntime
from v2.runtime.assembly import MechanicalVerifier, build_runtime, capability_catalog
from v2.runtime.ledger import LedgerKind, RunLedger
from v2.runtime.policy import ExecutionPolicy
from v2.runtime.recording import RecordedCapability

class ScriptedModel:
    def __init__(self, actions):
        self.actions = list(actions)
        self.calls = []

    async def generate(self, *, schema, prompt, payload, envelope, decode=None):
        self.calls.append(payload)
        value = self.actions.pop(0)
        return schema.model_validate(
            value if "step" in value else {"step": value})

class StubIntake:
    def __init__(self, task):
        self.task = task
        self.calls = 0

    async def understand(self, request, context=()):
        self.calls += 1
        return self.task

class PassSemantic:
    async def verify(self, task, draft, evidence):
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

def tool_action():
    return {"action": "tool", "capability": "standings", "node_id": "facts",
            "arguments": {"season": "2024-25"}}

def answer():
    binding = EvidenceOutputBinding(
        requirement_kind="task", requirement_id=None, output_id="WINS",
        node_id="facts", evidence_id="evidence:facts",
        selector="rows[0].WINS", row_selector="rows[0]",
        value={"kind": "integer", "value": 61},
        subject_entity_type="team", subject_entity_id="1610612738",
        subject_selector="rows[0].TEAM_ID",
        unit={"kind": "declared", "value": "count"}, domain="standings")
    return {"action": "answer", "draft": DraftReport(
        sections=["Record"], claims=[Claim(
            text="Boston Celtics won 61 games.", kind="observed",
            evidence_ids=["evidence:facts"], output_bindings=[binding])]
    ).model_dump(mode="json")}

def build_action_runtime(ledger, run_id="runtime-test"):
    scripted = ScriptedModel([tool_action(), answer()])
    model = RecordedStructuredModel(scripted, ledger, turn_id=run_id)
    caps = {"standings": RecordedCapability(
        FakeCapability("standings", [{"TEAM_ID": 1610612738,
                                      "TEAM_NAME": "Boston Celtics",
                                      "WINS": 61, "LOSSES": 21}]),
        ledger, turn_id=run_id)}
    catalog = capability_catalog()
    intake = StubIntake(task())
    runtime = ActionRuntime(
        intake=intake, model=model,
        executor=PlanExecutor(caps), mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=PassSemantic(), ledger=ledger,
        tool_catalog={"standings": catalog["standings"]},
        run_timeout_s=5, provider="offline", model_name="scripted")
    return runtime, scripted, intake

@pytest.mark.anyio
async def test_action_runtime_uses_one_turn_and_one_intake():
    ledger = RunLedger("runtime-test")
    runtime, scripted, intake = build_action_runtime(ledger)
    result = await runtime.run("wins", run_id="runtime-test")
    assert intake.calls == 1
    assert len(result.verified_claims) == 1
    assert result.verification.status == VerificationStatus.PASS
    assert [(item.output_id, item.status) for item in result.output_statuses] == [
        ("WINS", "complete")]
    assert len(scripted.calls) == 2
    starts = [item for item in ledger.entries if item.kind == LedgerKind.TURN_START]
    ends = [item for item in ledger.entries if item.kind == LedgerKind.TURN_END]
    assert len(starts) == len(ends) == 1

def test_build_runtime_action_loop_is_opt_in():
    policy = ExecutionPolicy.live()
    experimental, _ = build_runtime(
        provider="reflection", model_name="Beam-1.0-501B-A23B",
        run_id="factory-action", policy=policy, action_loop=True)
    staged, _ = build_runtime(
        provider="reflection", model_name="Beam-1.0-501B-A23B",
        run_id="factory-staged", policy=policy, action_loop=False)
    assert isinstance(experimental, ActionRuntime)
    assert isinstance(staged, Runtime)

@pytest.mark.anyio
async def test_action_loop_mode_streams_answer_citations_and_carry(monkeypatch, tmp_path):
    from v2.api import routes

    built = []

    def build(**kwargs):
        assert kwargs["action_loop"] is True
        ledger = RunLedger(kwargs["run_id"])
        runtime, _, _ = build_action_runtime(ledger, kwargs["run_id"])
        built.append(ledger)
        return runtime, ledger

    monkeypatch.setattr(routes, "runtime_v2_mode", lambda: "action_loop")
    monkeypatch.setattr("shared.providers.resolve_model_id",
                        lambda value: ("openrouter", "fixture"))
    monkeypatch.setattr("v2.runtime.assembly.build_runtime", build)
    monkeypatch.setattr(routes, "_PROJECTS", ProjectStore(tmp_path / "p.sqlite"))
    monkeypatch.setenv("DIME_V2_ACTIVITY_DIR", str(tmp_path / "activity"))

    response = await routes.quick_answer_stream(routes.QuickAnswerBody(q="wins"))
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    text = "".join(chunks)
    assert "event: final_answer" in text
    assert "event: graph_end" in text
    payload = json.loads(
        text.split("event: final_answer\ndata: ", 1)[1].split("\n\n", 1)[0])
    carry = payload["carry"]
    assert carry["verified_claims"] == 1
    assert carry["output_statuses"][0]["status"] == "complete"
    assert carry["citations"]
    assert payload["text"].strip()
    assert built
