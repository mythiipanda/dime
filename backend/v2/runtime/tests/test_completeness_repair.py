from __future__ import annotations

import os
from pathlib import Path

import pytest
from v2.contracts import Claim, ClaimKind, DraftReport, Plan, PlanNode, RunMode, TaskSpec, VerificationReport, VerificationStatus
from v2.runtime import FakeCapability, PlanExecutor, Runtime
from v2.runtime.assembly import MechanicalVerifier

BACKEND = Path(__file__).resolve().parents[3]
RUNTIME_WAREHOUSE = Path(os.environ.get("DIME_WAREHOUSE") or
                         BACKEND / "data" / "warehouse-runtime.duckdb")

@pytest.fixture
def anyio_backend():
    return "asyncio"

def _task():
    from v2.contracts import EvidenceRequirement
    return TaskSpec(
        goal="sample",
        mode=RunMode.QUICK,
        deliverable="answer",
        requested_outputs=["WINS", "LOSSES"],
        requirements=[EvidenceRequirement(
            id="stats",
            description="record",
            capability_options=["standings"],
            requested_outputs=["WINS", "LOSSES"],
        )],
    )

class _Intake:
    async def understand(self, request: str):
        return _task()

class _Planner:
    async def plan(self, task, failure_context=None):
        return Plan(nodes=[PlanNode(
            id="facts",
            description="facts",
            capability_hints=["standings"],
            covers_requirement_ids=["stats"],
        )])

def _binding(output_id, value):
    from v2.contracts import EvidenceOutputBinding
    return EvidenceOutputBinding(
        requirement_kind="task",
        requirement_id=None,
        output_id=output_id,
        node_id="facts",
        evidence_id="evidence:facts",
        selector=f"rows.{output_id}",
        value={"kind": "integer", "value": value},
        unit={"kind": "declared", "value": "count"},
        domain="standings",
    )

class _OmitSynth:
    async def synthesize(self, task, evidence):
        envelope = next(iter(evidence))
        return DraftReport(
            sections=["Answer"],
            claims=[Claim(
                text="61 wins",
                kind=ClaimKind.OBSERVED,
                evidence_ids=[envelope.evidence_id],
                output_bindings=[_binding("WINS", 61)],
            )],
        )

class _FullSynth:
    async def synthesize(self, task, evidence):
        envelope = next(iter(evidence))
        return DraftReport(
            sections=["Answer"],
            claims=[Claim(
                text="61 wins and 21 losses",
                kind=ClaimKind.OBSERVED,
                evidence_ids=[envelope.evidence_id],
                output_bindings=[_binding("WINS", 61), _binding("LOSSES", 21)],
            )],
        )

class _PassSemantic:
    async def verify(self, task, draft, evidence):
        return VerificationReport(
            status=VerificationStatus.PASS,
            claim_results=[{"claim_index": index, "supported": True} for index, _ in enumerate(draft.claims)],
        )

def _runtime(synth, repairer):
    return Runtime(
        intake=_Intake(),
        planner=_Planner(),
        executor=PlanExecutor({"standings": FakeCapability("standings", {"WINS": 61, "LOSSES": 21})}),
        synthesizer=synth,
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=_PassSemantic(),
        repairer=repairer,
    )

@pytest.mark.anyio
async def test_omitted_output_repairs_with_missing_output_named():
    seen = {}

    class _Repair:
        async def repair(self, task, draft, evidence, verification):
            seen["instructions"] = [*verification.missing_branches, *verification.repair_instructions]
            envelope = next(iter(evidence.values()))
            return DraftReport(
                sections=["Answer"],
                claims=[Claim(
                    text="61 wins and 21 losses",
                    kind=ClaimKind.OBSERVED,
                    evidence_ids=[envelope.evidence_id],
                    output_bindings=[_binding("WINS", 61), _binding("LOSSES", 21)],
                )],
            )

    result = await _runtime(_OmitSynth(), _Repair()).run("sample")
    assert result.repaired is True
    assert result.verification.status == VerificationStatus.PASS
    joined = " ".join(seen["instructions"])
    assert "LOSSES" in joined

@pytest.mark.anyio
async def test_repeated_omission_fails_loud_with_output_and_column():
    class _StubbornRepair:
        async def repair(self, task, draft, evidence, verification):
            return draft

    result = await _runtime(_OmitSynth(), _StubbornRepair()).run("sample")
    assert result.verification.status == VerificationStatus.PARTIAL
    assert result.repaired is True
    joined = " ".join([gap.message for gap in result.gaps] + result.draft.gaps)
    assert "LOSSES" in joined
    assert "standings" in joined

@pytest.mark.anyio
async def test_complete_synthesis_passes_without_repair():
    class _NoRepair:
        async def repair(self, task, draft, evidence, verification):
            raise AssertionError("repair must not run")

    result = await _runtime(_FullSynth(), _NoRepair()).run("sample")
    assert result.repaired is False
    assert result.verification.status == VerificationStatus.PASS

@pytest.mark.skipif(
    not RUNTIME_WAREHOUSE.exists(),
    reason=f"the runtime warehouse is absent at {RUNTIME_WAREHOUSE}")
@pytest.mark.anyio
async def test_mvp_winner_and_share_publish_through_real_award_tool(monkeypatch, tmp_path):
    from v2.contracts import EvidenceOutputBinding, SeasonRef
    from v2.adapters.core import ToolCapability

    from shared import store
    from shared.tools import _core
    from v2.adapters import coverage
    connect = store.connect
    monkeypatch.setattr(store, "DB_PATH", RUNTIME_WAREHOUSE)
    monkeypatch.setattr(store, "connect", lambda read_only=True: connect(read_only=True))
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    store.warehouse_identity_cache_clear()
    _core.last_completed_season_cache_clear()
    coverage.coverage_cache_clear()
    try:
        from v2.adapters import acall_capability
        probe = await acall_capability("award_results", {"view": "winner", "award": "MVP", "season": "2023-24"})
    finally:
        store.warehouse_tables_cache_clear()
        store.warehouse_pool_clear()
        store.warehouse_identity_cache_clear()
        _core.last_completed_season_cache_clear()
        coverage.coverage_cache_clear()
    assert probe.rows[0]["award_share"] == 0.935
    winner = probe.rows[0]["player"]
    share = float(probe.rows[0]["award_share"])
    task = TaskSpec(
        goal="sample",
        mode=RunMode.QUICK,
        deliverable="answer",
        requested_outputs=["PLAYER_NAME", "VOTE_SHARE"],
        season=SeasonRef(value="2023-24", source="user", confidence=1.0),
    )

    class _MvpIntake:
        async def understand(self, request: str):
            return task

    class _MvpPlanner:
        async def plan(self, task, failure_context=None):
            return Plan(nodes=[PlanNode(
                id="mvp_winner",
                description="official 2023-24 MVP result",
                capability_hints=["award_results"],
                arguments={"view": "winner", "award": "MVP"},
            )])

    class _MvpSynth:
        async def synthesize(self, task, evidence):
            envelope = next(iter(evidence))
            row = envelope.rows[0]
            return DraftReport(
                sections=["MVP"],
                claims=[Claim(
                    text=f"{row['player']} won with {row['award_share']} share.",
                    kind=ClaimKind.OBSERVED,
                    evidence_ids=[envelope.evidence_id],
                    output_bindings=[
                        EvidenceOutputBinding(
                            requirement_kind="task",
                            requirement_id=None,
                            output_id="PLAYER_NAME",
                            node_id="mvp_winner",
                            evidence_id=envelope.evidence_id,
                            selector="rows[0].player",
                            value={"kind": "string", "value": str(row["player"])},
                            unit={"kind": "unitless"},
                            domain="award_results",
                        ),
                        EvidenceOutputBinding(
                            requirement_kind="task",
                            requirement_id=None,
                            output_id="VOTE_SHARE",
                            node_id="mvp_winner",
                            evidence_id=envelope.evidence_id,
                            selector="rows[0].award_share",
                            value={"kind": "float", "value": float(row["award_share"])},
                            unit={"kind": "declared", "value": "fraction_0_1"},
                            domain="award_results",
                        ),
                    ],
                )],
            )

    instance = Runtime(
        intake=_MvpIntake(),
        planner=_MvpPlanner(),
        executor=PlanExecutor({"award_results": ToolCapability("award_results")}),
        synthesizer=_MvpSynth(),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=_PassSemantic(),
        repairer=None,
    )
    result = await instance.run("sample")
    assert result.verification.status == VerificationStatus.PASS
    assert result.repaired is False
    by_output = {item.output_id: item for item in result.output_statuses if item.requirement_kind == "task"}
    assert by_output["PLAYER_NAME"].status == "complete"
    assert by_output["VOTE_SHARE"].status == "complete"
    assert by_output["PLAYER_NAME"].binding.value.value == winner
    assert by_output["VOTE_SHARE"].binding.value.value == share
