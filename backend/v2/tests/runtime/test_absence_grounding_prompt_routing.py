from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from v2 import prompts as prompts_module
from v2.adapters.models import ModelSemanticVerifier, ModelSynthesizer
from v2.contracts import Claim, ClaimKind, DraftReport, EvidenceEnvelope, TaskSpec
from v2.prompts import load_prompt

PROMPTS_DIR = Path(prompts_module.__file__).parent


class StageBoundary(BaseException):
    pass


class RecordingPromptModel:
    def __init__(self) -> None:
        self.prompts: dict[str, str] = {}

    async def generate(self, *, schema, prompt, payload, envelope,
                       decode=None) -> Any:
        self.prompts[envelope.route] = prompt
        raise StageBoundary(envelope.route)


def _task() -> TaskSpec:
    return TaskSpec.model_validate({
        "goal": "Report the 2024-25 assists leader.",
        "mode": "quick",
        "deliverable": "The assists leader with games played.",
        "required_evidence": ["qualified_leaders"],
    })


def _evidence(task: TaskSpec) -> dict[str, EvidenceEnvelope]:
    return {"evidence:n1": EvidenceEnvelope(
        evidence_id="evidence:n1", capability="qualified_leaders",
        source="fake", observed_at=datetime.now(UTC),
        season=task.season.value if task.season else None, rows=[])}


def _draft() -> DraftReport:
    return DraftReport.model_validate({
        "sections": ["Assists leader"],
        "claims": [Claim(text="The assists leader led the league.",
                         kind=ClaimKind.OBSERVED,
                         evidence_ids=["evidence:n1"])],
    })


@pytest.mark.anyio
async def test_synthesizer_route_request_carries_dev_prompt_with_absence_invariant():
    model = RecordingPromptModel()
    stage = ModelSynthesizer(model, provider="probe", model_name="probe-model")
    task = _task()
    with pytest.raises(StageBoundary):
        await stage.synthesize(task, list(_evidence(task).values()))
    captured = model.prompts["synthesizer"]
    assert captured == (PROMPTS_DIR / "synthesizer.md").read_text(encoding="utf-8")
    assert captured == load_prompt("synthesizer")
    assert ("a failed or empty query, or row-count or freshness metadata "
            "alone never proves a source, metric, or field absent") in captured
    assert ("direct, explicitly named source, field, or time-window metadata "
            "does support a claim about exactly what it enumerates") in captured


@pytest.mark.anyio
async def test_semantic_verifier_route_request_carries_dev_prompt_with_absence_invariant():
    model = RecordingPromptModel()
    stage = ModelSemanticVerifier(model, provider="probe", model_name="probe-model")
    task = _task()
    with pytest.raises(StageBoundary):
        await stage.verify(task, _draft(), _evidence(task))
    captured = model.prompts["semantic_verifier"]
    assert captured == (PROMPTS_DIR / "verifier.md").read_text(encoding="utf-8")
    assert captured == load_prompt("verifier")
    assert ("rests on a non-exhaustive table or column list, a failed or empty "
            "query, or freshness counts alone") in captured
    assert (
        "generalizes from partial inspection to a whole corpus, source, or metric"
    ) in captured
    assert ("a bounded claim from direct, named source, field, or time-window "
            "metadata") in captured


def test_absence_disclaimer_rule_present_in_both_prompts():
    assert ("A later disclaimer never licenses an earlier unsupported "
            "availability or absence claim.") in load_prompt("synthesizer")
    assert ("A later disclaimer does not excuse an earlier unsupported "
            "availability or absence claim.") in load_prompt("verifier")


def test_stored_manifest_candidate_prompt_hashes_match_live_and_others_retained():
    manifest = json.loads(
        (PROMPTS_DIR.parent / "schema_snapshots" / "manifest.json").read_text())
    prompt_sha256 = manifest["prompt_sha256"]
    for name in ("synthesizer", "verifier"):
        live = hashlib.sha256(load_prompt(name).encode()).hexdigest()
        assert prompt_sha256[name] == live, (
            f"{name}.md changed without a manifest prompt_sha256 update")
    retained = {
        "intake": "30deed35ee933962d6b0ae4dc4a8a646c06442804dbda3560aef792f7e086ec6",
        "planner": "65291f1eecaa5c2d6a1abd63974675bee765afeebf7905ad7fd793cfd26d679b",
        "planner_v3": "52ccf42eeca25084129559a45316a8a646d3edbc99b25aeda2e424a3be27d534",
        "project_planner": "4e49203f74c7967dabaf15cd7a3fe849cd80b0e1945487ac9eb28269293a0386",
        "repair": "669fd8c8cfc60e423b46f756b56b474d2ae3dae5361decbfd12bcd15fa6419b3",
        "repair_answer": "bf514dce7fe29b2db50e443561e2c76f4efeca0a4e39c6d42f8fecdd85bf6c4c",
        "requirement_review": "f87e6f84dd5218723e6040ef081391787a47d433c5c58355b30919cd8c95b020",
        "requirement_review_v3": "a0a747ffcee1ff6757e8aaf3dca9fc9f96ea4a0e5d21af239a4888700f302a53",
    }
    assert len(prompt_sha256) == len(retained) + 2
    for name, digest in retained.items():
        assert prompt_sha256[name] == digest, (
            f"manifest prompt_sha256[{name}] was rebaselined outside this change")


def test_preflight_accepts_expected_candidate_and_rejects_prompt_tamper(
        monkeypatch, tmp_path):
    from v2.api import routes
    monkeypatch.setattr(routes, "runtime_warehouse_identity", lambda: {
        "warehouse_id": "test-warehouse", "sha256": "0" * 64,
        "sha256_derivation": "test-derivation"})
    routes.runtime_asset_manifest.cache_clear()
    try:
        observed = routes.runtime_asset_manifest().as_dict()
        expected_path = tmp_path / "expected_asset_manifest.json"
        expected_path.write_text(json.dumps(observed))
        assert routes.preflight_runtime_assets(expected_path).as_dict() == observed
        tampered = json.loads(json.dumps(observed))
        tampered["prompt_sha256"]["semantic_verifier"] = "deliberately-changed"
        tampered_path = tmp_path / "tampered_asset_manifest.json"
        tampered_path.write_text(json.dumps(tampered))
        with pytest.raises(RuntimeError, match="substantive mismatch"):
            routes.preflight_runtime_assets(tampered_path)
    finally:
        routes.runtime_asset_manifest.cache_clear()
