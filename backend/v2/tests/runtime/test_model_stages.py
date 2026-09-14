from datetime import UTC, datetime

import pytest

from v2.adapters.models import (
    ModelIntake,
    ModelPlanner,
    ModelSemanticVerifier,
    ModelSynthesizer,
    _json_object,
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


def test_json_object_accepts_fenced_json_and_rejects_prose():
    assert _json_object('```json\n{"ok": true}\n```') == '{"ok": true}'
    with pytest.raises(ValueError):
        _json_object("no object")
