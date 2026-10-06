from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))

WAREHOUSE = BACKEND / "data" / "warehouse.duckdb"

pytestmark = pytest.mark.skipif(
    not WAREHOUSE.exists(),
    reason=f"the warehouse is absent at {WAREHOUSE}")

@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param

def _stub_model_class():
    import importlib.util

    path = BACKEND / "v2" / "tests" / "runtime" / "test_model_stages.py"
    spec = importlib.util.spec_from_file_location("model_stages_stub", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.StubModel

def _real_catalog():
    from v2.runtime.assembly import capability_catalog

    return capability_catalog()

def _mvp_task(outputs):
    from v2.contracts import EvidenceRequirement, SeasonRef, TaskSpec

    return TaskSpec(
        goal="Who won the 2023-24 MVP and how large was the winning vote share?",
        mode="quick",
        deliverable="winner and share",
        requested_outputs=list(outputs),
        season=SeasonRef(value="2023-24", source="user", confidence=1.0),
        requirements=[EvidenceRequirement(
            id="mvp_result",
            description="official 2023-24 MVP result",
            capability_options=["award_results"],
            capability_arguments={"view": "winner", "award": "MVP", "season": "2023-24"},
            requested_outputs=list(outputs),
        )],
    )

def _planner_node(node_id, capability, arguments, covers=("mvp_result",)):
    return {
        "id": node_id,
        "description": "official MVP result",
        "capability": capability,
        "covers_requirement_ids": list(covers),
        "arguments": dict(arguments),
        "depends_on": None,
        "max_attempts": None,
        "status": None,
    }

@pytest.mark.anyio
async def test_unresolvable_output_is_rejected_with_vocabulary():
    from v2.adapters.models import ModelPlanner

    StubModel = _stub_model_class()
    planner = ModelPlanner(
        StubModel([{"nodes": [_planner_node(
            "mvp", "award_results",
            {"view": "winner", "award": "MVP", "season": "2023-24"})]}]),
        provider="stub", model_name="stub",
        capability_catalog=_real_catalog())
    task = _mvp_task(["HOME_RUNS"])
    with pytest.raises(ValueError, match="HOME_RUNS") as caught:
        await planner.plan(task)
    message = str(caught.value)
    assert "award_results" in message
    assert "VOTE_SHARE" in message or "AWARD_SHARE" in message or "PLAYER" in message

@pytest.mark.anyio
async def test_repaired_plan_with_servable_names_executes_and_publishes(real_warehouse):
    from v2.adapters import acall_capability
    from v2.adapters.capabilities import resolve_metric_column, CAPABILITIES
    from v2.adapters.models import ModelPlanner

    StubModel = _stub_model_class()
    spec = CAPABILITIES["award_results"]
    assert resolve_metric_column(spec, "HOME_RUNS") is None
    assert resolve_metric_column(spec, "PLAYER_NAME") is not None
    assert resolve_metric_column(spec, "VOTE_SHARE") is not None
    planner = ModelPlanner(
        StubModel([{"nodes": [_planner_node(
            "mvp", "award_results",
            {"view": "winner", "award": "MVP", "season": "2023-24"})]}]),
        provider="stub", model_name="stub",
        capability_catalog=_real_catalog())
    task = _mvp_task(["PLAYER_NAME", "VOTE_SHARE"])
    plan = await planner.plan(task)
    assert [node.id for node in plan.nodes] == ["mvp"]
    envelope = await acall_capability("award_results", {
        "view": "winner", "award": "MVP", "season": "2023-24"})
    assert envelope.rows[0]["player"] == "Nikola Jokić"
    assert envelope.rows[0]["award_share"] == pytest.approx(0.935)
    from v2.contracts import Claim, ClaimKind, DraftReport, EvidenceOutputBinding
    bindings = [
        EvidenceOutputBinding(
            requirement_kind="evidence", requirement_id="mvp_result",
            output_id="PLAYER_NAME", node_id="mvp",
            evidence_id=envelope.evidence_id, selector="rows[0].player",
            row_selector="rows[0]",
            value={"kind": "string", "value": str(envelope.rows[0]["player"])},
            subject_entity_type="player",
            subject_entity_id=str(envelope.rows[0]["player"]),
            subject_selector="rows[0].player",
            unit={"kind": "unitless"}, domain="award_results"),
        EvidenceOutputBinding(
            requirement_kind="evidence", requirement_id="mvp_result",
            output_id="VOTE_SHARE", node_id="mvp",
            evidence_id=envelope.evidence_id, selector="rows[0].award_share",
            row_selector="rows[0]",
            value={"kind": "float", "value": float(envelope.rows[0]["award_share"])},
            subject_entity_type="player",
            subject_entity_id=str(envelope.rows[0]["player"]),
            subject_selector="rows[0].player",
            unit={"kind": "declared", "value": "fraction_0_1"},
            domain="award_results"),
    ]
    from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings
    from v2.contracts import Plan, PlanNode, VerifiedClaim, ClaimSource
    execution = ExecutionResult(
        plan=Plan(nodes=[PlanNode(
            id="mvp", description="official MVP result",
            capability_hints=["award_results"],
            covers_requirement_ids=["mvp_result"],
            arguments={"view": "winner", "award": "MVP", "season": "2023-24"},
            status="complete")]),
        evidence_by_node={"mvp": envelope}, attempts={"mvp": 1})
    claim = Claim(text="winner line", kind=ClaimKind.OBSERVED,
                  evidence_ids=[envelope.evidence_id], output_bindings=bindings)
    draft = DraftReport(sections=["MVP"], claims=[claim])
    verified = VerifiedClaim(
        claim_index=0, claim=claim, evidence_ids=[envelope.evidence_id],
        sources=[ClaimSource(evidence_id=envelope.evidence_id, source=envelope.source,
                             capability=envelope.capability, observed_at=envelope.observed_at)],
        output_bindings=bindings)
    admitted = admit_verified_claim_bindings(task, execution, draft, verified)
    assert {binding.output_id for binding in admitted.output_bindings} == {"PLAYER_NAME", "VOTE_SHARE"}

@pytest.mark.anyio
async def test_servable_plan_is_unaffected():
    from v2.adapters.models import ModelPlanner

    StubModel = _stub_model_class()
    planner = ModelPlanner(
        StubModel([{"nodes": [_planner_node(
            "mvp", "award_results",
            {"view": "winner", "award": "MVP", "season": "2023-24"})]}]),
        provider="stub", model_name="stub",
        capability_catalog=_real_catalog())
    task = _mvp_task(["PLAYER_NAME", "VOTE_SHARE"])
    plan = await planner.plan(task)
    assert plan.nodes[0].covers_requirement_ids == ["mvp_result"]
    assert plan.nodes[0].capability_hints == ["award_results"]

@pytest.mark.anyio
async def test_mvp_publishes_with_stable_names_across_runs(real_warehouse):
    from v2.adapters import acall_capability
    from v2.adapters.models import ModelPlanner, servable_output_names

    StubModel = _stub_model_class()
    first = servable_output_names("award_results")
    second = servable_output_names("award_results")
    assert first == second
    assert "PLAYER_NAME" in first
    assert "VOTE_SHARE" in first
    names = ["PLAYER_NAME", "VOTE_SHARE"]
    published = []
    for index in range(2):
        planner = ModelPlanner(
            StubModel([{"nodes": [_planner_node(
                "mvp", "award_results",
                {"view": "winner", "award": "MVP", "season": "2023-24"})]}]),
            provider="stub", model_name="stub",
            capability_catalog=_real_catalog())
        plan = await planner.plan(_mvp_task(names))
        assert plan.nodes[0].capability_hints == ["award_results"]
        envelope = await acall_capability("award_results", {
            "view": "winner", "award": "MVP", "season": "2023-24"})
        published.append((envelope.rows[0]["player"], envelope.rows[0]["award_share"]))
    assert published[0] == published[1]
    assert published[0][0] == "Nikola Jokić"

@pytest.fixture
def real_warehouse(monkeypatch):
    from shared import store
    from shared.tools import _core
    from v2.adapters import coverage

    connect = store.connect
    monkeypatch.setattr(store, "DB_PATH", WAREHOUSE)
    monkeypatch.setattr(store, "CANONICAL_DB_PATH", WAREHOUSE)
    monkeypatch.setattr(
        store, "connect", lambda read_only=True: connect(read_only=True))
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    store.warehouse_identity_cache_clear()
    _core.last_completed_season_cache_clear()
    coverage.coverage_cache_clear()
    yield WAREHOUSE
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    store.warehouse_identity_cache_clear()
    _core.last_completed_season_cache_clear()
    coverage.coverage_cache_clear()
