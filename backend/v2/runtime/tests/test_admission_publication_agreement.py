from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

FIXTURES = BACKEND / "tests" / "fixtures" / "bbref_awards"
SEASON = "2023-24"
AS_OF = date(2026, 9, 8)


def _page(year: int):
    def transport(url: str) -> str:
        return (FIXTURES / f"awards_{year}.html").read_text(encoding="utf-8")

    return transport


@pytest.fixture(scope="module")
def recorded_awards(tmp_path_factory):
    import seed_bbref_awards as seed
    from shared import store

    root = tmp_path_factory.mktemp("v2_admit_publish_agreement")
    recorded = root / "recorded.duckdb"
    original = (store.DB_PATH, store.LOCK_PATH)
    store.DB_PATH = recorded
    store.LOCK_PATH = root / ".write.lock"
    try:
        seed.seed_season(SEASON, transport=_page(2024), min_interval_s=0.0)
    finally:
        store.DB_PATH, store.LOCK_PATH = original
    return recorded


@pytest.fixture
def awards_warehouse(recorded_awards, tmp_path, monkeypatch):
    from shared import store
    from shared.tools import _core
    from v2.adapters import coverage

    path = tmp_path / "awards.duckdb"
    shutil.copyfile(recorded_awards, path)
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    store.warehouse_identity_cache_clear()
    _core.last_completed_season_cache_clear()
    coverage.coverage_cache_clear()
    return path


@pytest.fixture(autouse=True)
def _open_chat_budget():
    from v2.api import routes

    routes._CHAT_HITS.clear()
    yield
    routes._CHAT_HITS.clear()


def _flat_envelope():
    from v2.contracts import EntityRef, EvidenceEnvelope

    team = EntityRef(id="1610612738", type="team", display_name="North Bay Kings")
    return EvidenceEnvelope(
        evidence_id="evidence:flat",
        capability="matchup_brief",
        source="silver_team_ratings:fetch_matchup:warehouse",
        observed_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
        season="2024-25",
        as_of=date(2026, 9, 8),
        entities=[team],
        rows=[{"TEAM_ID": 1610612738, "OFF_RATING": 116.6}],
        units={"OFF_RATING": "points_per_100_possessions"},
        source_identity={"kind": "warehouse", "warehouse_id": "frozen-eval",
                          "sha256": "a" * 64},
    )


def _admit(task, execution, draft, verified):
    from v2.runtime.models import admit_verified_claim_bindings

    return admit_verified_claim_bindings(task, execution, draft, verified)


def _publish_trace(envelope, binding):
    from v2.api.routes import _traced_value

    return _traced_value(envelope, binding)


def test_mvp_winner_and_share_publish_with_citations_through_real_tool(
        awards_warehouse, monkeypatch, tmp_path):
    import json as _json

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from v2.adapters import call_capability
    from v2.adapters.core import ToolCapability
    from v2.api import routes
    from v2.contracts import (
        Claim, ClaimKind, DraftReport, EvidenceOutputBinding, Plan, PlanNode,
        RunMode, SeasonRef, TaskSpec, VerificationReport, VerificationStatus,
    )
    from v2.projects.service import ProjectStore
    from v2.runtime import PlanExecutor, Runtime
    from v2.runtime.assembly import MechanicalVerifier
    from v2.runtime.ledger import RunLedger

    probe = call_capability(
        "award_results", {"view": "winner", "award": "MVP", "season": SEASON})
    assert probe.rows["placements"][0]["award_share"] == 0.935
    placement = probe.rows["placements"][0]

    task = TaskSpec(
        goal="Who won the 2023-24 MVP and how large was the winning vote share?",
        mode=RunMode.QUICK,
        deliverable="winner and share",
        requested_outputs=["PLAYER_NAME", "VOTE_SHARE"],
        season=SeasonRef(value=SEASON, source="user", confidence=1.0))

    class Intake:
        async def understand(self, request: str, context=()):
            return task

    class Planner:
        async def plan(self, task, failure_context=None):
            return Plan(nodes=[PlanNode(
                id="mvp_winner", description="official 2023-24 MVP result",
                capability_hints=["award_results"],
                arguments={"view": "winner", "award": "MVP"})])

    class Synthesizer:
        async def synthesize(self, task, evidence):
            envelope = next(iter(evidence))
            row = envelope.rows["placements"][0]
            return DraftReport(
                sections=["MVP"],
                claims=[Claim(
                    text=(f"{row['player']} won with {row['award_share']} share."),
                    kind=ClaimKind.OBSERVED,
                    evidence_ids=[envelope.evidence_id],
                    output_bindings=[
                        EvidenceOutputBinding(
                            requirement_kind="task", requirement_id=None,
                            output_id="PLAYER_NAME", node_id="mvp_winner",
                            evidence_id=envelope.evidence_id,
                            selector="rows[0].player",
                            value={"kind": "string", "value": str(row["player"])},
                            unit={"kind": "unitless"},
                            domain="award_results"),
                        EvidenceOutputBinding(
                            requirement_kind="task", requirement_id=None,
                            output_id="VOTE_SHARE", node_id="mvp_winner",
                            evidence_id=envelope.evidence_id,
                            selector="rows[0].award_share",
                            value={"kind": "float",
                                   "value": float(row["award_share"])},
                            unit={"kind": "declared", "value": "fraction_0_1"},
                            domain="award_results"),
                    ])])

    class Semantic:
        async def verify(self, task, draft, evidence):
            return VerificationReport(
                status=VerificationStatus.PASS,
                claim_results=[{"claim_index": 0, "supported": True}])

    runtime = Runtime(
        intake=Intake(), planner=Planner(),
        executor=PlanExecutor({"award_results": ToolCapability("award_results")}),
        synthesizer=Synthesizer(),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=Semantic())

    def build(**kwargs):
        return runtime, RunLedger(kwargs["run_id"])

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setattr("shared.providers.resolve_model_id",
                        lambda value: ("openrouter", "fixture"))
    monkeypatch.setattr("v2.runtime.assembly.build_runtime", build)
    monkeypatch.setattr(routes, "_PROJECTS", ProjectStore(tmp_path / "p.sqlite"))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post(
        "/api/v2/chat/stream",
        json={"q": "Who won the 2023-24 MVP and how large was the winning vote share?"})
    assert response.status_code == 200

    def event(name: str) -> dict:
        payloads = [chunk.split("data: ", 1)[1]
                    for chunk in response.text.split("\n\n")
                    if chunk.startswith(f"event: {name}\n")]
        assert payloads
        return _json.loads(payloads[-1])

    custom = event("custom_data")
    final = event("final_answer")
    cited = {row["output_id"]: row["value"] for row in custom["tables"]}
    assert cited["PLAYER_NAME"] == placement["player"]
    assert cited["VOTE_SHARE"] == str(placement["award_share"])
    assert {row["provenance"]["capability"] for row in custom["tables"]} == {
        "award_results"}
    assert {row["provenance"]["origin"] for row in custom["tables"]} == {
        "warehouse"}
    assert custom["unverified_numbers"] == []
    assert "I could not verify a publishable answer" not in final["text"]


def test_flat_envelope_capability_is_unaffected():
    from v2.contracts import (
        Claim, ClaimKind, DraftReport, EvidenceOutputBinding, Plan, PlanNode,
        RunMode, SeasonRef, TaskSpec, VerifiedClaim, ClaimSource,
    )
    from v2.runtime.models import ExecutionResult

    envelope = _flat_envelope()
    binding = EvidenceOutputBinding(
        requirement_kind="task", requirement_id=None, output_id="OFF_RATING",
        node_id="flat", evidence_id=envelope.evidence_id,
        selector="rows[0].OFF_RATING",
        value={"kind": "float", "value": 116.6},
        unit={"kind": "declared", "value": "points_per_100_possessions"},
        domain="matchup_brief")
    task = TaskSpec(
        goal="flat", mode=RunMode.QUICK, deliverable="flat",
        requested_outputs=["OFF_RATING"],
        season=SeasonRef(value="2024-25", source="user", confidence=1.0))
    plan = Plan(nodes=[PlanNode(
        id="flat", description="flat", capability_hints=["matchup_brief"],
        status="complete")])
    execution = ExecutionResult(
        plan=plan, evidence_by_node={"flat": envelope}, attempts={"flat": 1})
    claim = Claim(text="flat 116.6", kind=ClaimKind.OBSERVED,
                  evidence_ids=[envelope.evidence_id], output_bindings=[binding])
    verified = VerifiedClaim(
        claim_index=0, claim=claim, evidence_ids=[envelope.evidence_id],
        sources=[ClaimSource(evidence_id=envelope.evidence_id,
                             source=envelope.source,
                             capability=envelope.capability)],
        output_bindings=[binding])
    admitted = _admit(
        task, execution, DraftReport(sections=["x"], claims=[claim]), verified)
    assert len(admitted.output_bindings) == 1
    value, reason = _publish_trace(envelope, binding)
    assert reason is None
    assert value == 116.6


def test_selector_naming_nothing_is_rejected_by_both():
    from v2.contracts import (
        Claim, ClaimKind, DraftReport, EvidenceOutputBinding, Plan, PlanNode,
        RunMode, SeasonRef, TaskSpec, VerifiedClaim, ClaimSource,
    )
    from v2.runtime.models import (
        AmbiguousSelector, ExecutionResult, UnresolvedSelector,
        resolve_evidence_binding,
    )

    envelope = _flat_envelope()
    envelope = envelope.model_copy(update={
        "rows": [{"TEAM_ID": 1610612738}],
    })
    binding = EvidenceOutputBinding(
        requirement_kind="task", requirement_id=None, output_id="OFF_RATING",
        node_id="flat", evidence_id=envelope.evidence_id,
        selector="rows[0].OFF_RATING",
        value={"kind": "float", "value": 1.0},
        unit={"kind": "declared", "value": "points_per_100_possessions"},
        domain="matchup_brief")
    resolution = resolve_evidence_binding(envelope, binding, None)
    assert isinstance(resolution, UnresolvedSelector)
    assert not isinstance(resolution, AmbiguousSelector)
    value, reason = _publish_trace(envelope, binding)
    assert value is None
    assert reason is not None
    task = TaskSpec(
        goal="flat", mode=RunMode.QUICK, deliverable="flat",
        requested_outputs=["OFF_RATING"],
        season=SeasonRef(value="2024-25", source="user", confidence=1.0))
    plan = Plan(nodes=[PlanNode(
        id="flat", description="flat", capability_hints=["matchup_brief"],
        status="complete")])
    execution = ExecutionResult(
        plan=plan, evidence_by_node={"flat": envelope}, attempts={"flat": 1})
    claim = Claim(text="missing", kind=ClaimKind.OBSERVED,
                  evidence_ids=[envelope.evidence_id], output_bindings=[binding])
    verified = VerifiedClaim(
        claim_index=0, claim=claim, evidence_ids=[envelope.evidence_id],
        sources=[ClaimSource(evidence_id=envelope.evidence_id,
                             source=envelope.source,
                             capability=envelope.capability)],
        output_bindings=[binding])
    with pytest.raises(ValueError, match="exactly one value"):
        _admit(task, execution, DraftReport(sections=["x"], claims=[claim]),
               verified)


def test_admission_and_publication_agree_by_construction_on_nested_envelope(
        awards_warehouse):
    from v2.adapters import call_capability
    from v2.api import routes
    from v2.runtime import models

    import inspect as _inspect

    source = _inspect.getsource(routes._traced_value)
    assert "resolve_evidence_binding" in source
    assert "resolve_subject_row" in source
    envelope = call_capability(
        "award_results", {"view": "winner", "award": "MVP", "season": SEASON})
    assert isinstance(envelope.rows, dict)
    assert envelope.rows["placements"][0]["award_share"] == 0.935
    seen = []

    real = models.resolve_evidence_binding

    def spy(evidence, binding, subject_row):
        seen.append((binding.selector, subject_row))
        return real(evidence, binding, subject_row)

    from v2.contracts import EvidenceOutputBinding

    good = EvidenceOutputBinding(
        requirement_kind="task", requirement_id=None, output_id="VOTE_SHARE",
        node_id="mvp_winner", evidence_id=envelope.evidence_id,
        selector="rows[0].award_share",
        value={"kind": "float", "value": 0.935},
        unit={"kind": "declared", "value": "fraction_0_1"},
        domain="award_results")
    missing = good.model_copy(update={
        "selector": "rows[0].NO_SUCH_COLUMN",
        "value": {"kind": "float", "value": 1.0},
    })
    import v2.runtime.models as models_module

    monkey = pytest.MonkeyPatch()
    monkey.setattr(models_module, "resolve_evidence_binding", spy)
    try:
        value, reason = routes._traced_value(envelope, good)
        assert value == 0.935
        assert reason is None
        value, reason = routes._traced_value(envelope, missing)
        assert value is None
        assert reason is not None
        publication_calls = list(seen)
        seen.clear()
        from v2.contracts import (
            Claim, ClaimKind, DraftReport, Plan, PlanNode, RunMode, SeasonRef,
            TaskSpec, VerifiedClaim, ClaimSource,
        )
        from v2.runtime.models import ExecutionResult

        task = TaskSpec(
            goal="agreement", mode=RunMode.QUICK, deliverable="agreement",
            requested_outputs=["VOTE_SHARE"],
            season=SeasonRef(value=SEASON, source="user", confidence=1.0))
        plan = Plan(nodes=[PlanNode(
            id="mvp_winner", description="mvp", capability_hints=["award_results"],
            status="complete")])
        execution = ExecutionResult(
            plan=plan, evidence_by_node={"mvp_winner": envelope},
            attempts={"mvp_winner": 1})
        claim = Claim(text="share", kind=ClaimKind.OBSERVED,
                      evidence_ids=[envelope.evidence_id], output_bindings=[good])
        verified = VerifiedClaim(
            claim_index=0, claim=claim, evidence_ids=[envelope.evidence_id],
            sources=[ClaimSource(evidence_id=envelope.evidence_id,
                                 source=envelope.source,
                                 capability=envelope.capability)],
            output_bindings=[good])
        admitted = models_module.admit_verified_claim_bindings(
            task, execution, DraftReport(sections=["x"], claims=[claim]),
            verified)
        assert len(admitted.output_bindings) == 1
        bad_claim = Claim(text="missing", kind=ClaimKind.OBSERVED,
                          evidence_ids=[envelope.evidence_id],
                          output_bindings=[missing])
        bad_verified = VerifiedClaim(
            claim_index=0, claim=bad_claim, evidence_ids=[envelope.evidence_id],
            sources=[ClaimSource(evidence_id=envelope.evidence_id,
                                 source=envelope.source,
                                 capability=envelope.capability)],
            output_bindings=[missing])
        with pytest.raises(ValueError):
            models_module.admit_verified_claim_bindings(
                task, execution, DraftReport(sections=["x"], claims=[bad_claim]),
                bad_verified)
        admission_calls = list(seen)
        assert publication_calls and admission_calls
        assert publication_calls[0][0] == admission_calls[0][0] == "rows[0].award_share"
    finally:
        monkey.undo()


def test_reanchor_consults_shared_selector_instead_of_exact_path():
    import v2.runtime.models as models_module

    seen = []
    real = models_module.resolve_selector

    def spy(envelope, selector, **kwargs):
        seen.append(selector)
        return real(envelope, selector, **kwargs)

    monkey = pytest.MonkeyPatch()
    monkey.setattr(models_module, "resolve_selector", spy)
    try:
        from v2.contracts import EvidenceOutputBinding
        from v2.runtime.models import _reanchor_binding
        from v2.adapters import call_capability  # noqa: F401

        envelope = _flat_envelope()
        envelope = envelope.model_copy(update={
            "rows": [
                {"TEAM_ID": 999, "OFF_RATING": 100.0},
                {"TEAM_ID": 1610612738, "OFF_RATING": 116.6},
            ],
        })
        binding = EvidenceOutputBinding(
            requirement_kind="task", requirement_id=None, output_id="OFF_RATING",
            node_id="flat", evidence_id=envelope.evidence_id,
            selector="rows[0].OFF_RATING", row_selector="rows[0]",
            subject_entity_type="team", subject_entity_id="1610612738",
            subject_selector="rows[0].TEAM_ID",
            value={"kind": "float", "value": 116.6},
            unit={"kind": "declared", "value": "points_per_100_possessions"},
            domain="matchup_brief")
        _reanchor_binding(binding, envelope)
        assert seen, "reanchor must consult the shared selector"
        assert "rows[1].OFF_RATING" in seen
    finally:
        monkey.undo()
