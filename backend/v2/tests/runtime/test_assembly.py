from datetime import UTC, datetime

import pytest

from v2.adapters.core import ToolCapability
from v2.contracts import PlanNode, SeasonRef, TaskSpec


@pytest.mark.anyio
async def test_tool_capability_uses_planned_arguments_and_scoped_season():
    seen = {}

    class Tool:
        async def ainvoke(self, arguments):
            seen.update(arguments)
            return {"ok": True, "rows": [{"TEAM": "Boston"}],
                    "meta": {"source": "fixture"}}

    node = PlanNode(
        id="standings", description="record", capability_hints=["standings"],
        arguments={"team_id": "1610612738"}, completion_test="one row")
    task = TaskSpec(
        goal="Boston record", mode="quick", deliverable="record",
        season=SeasonRef(value="2025-26", source="user", confidence=1))
    result = await ToolCapability(
        "standings", tools={"get_standings": Tool()}).execute(node, task, [])

    assert seen == {"team_id": "1610612738", "season": "2025-26"}
    assert result.capability == "standings"


@pytest.mark.anyio
async def test_seasonless_capability_does_not_receive_season():
    seen = {}

    class Tool:
        async def ainvoke(self, arguments):
            seen.update(arguments)
            return {"ok": True, "rows": {"players": [], "teams": []},
                    "meta": {"source": "fixture"}}

    node = PlanNode(
        id="resolve", description="resolve", capability_hints=["entity_resolution"],
        arguments={"query": "Boston"}, completion_test="one team")
    task = TaskSpec(
        goal="Boston record", mode="quick", deliverable="record",
        season=SeasonRef(value="2025-26", source="default", confidence=.8))
    await ToolCapability(
        "entity_resolution", tools={"resolve_entity": Tool()}).execute(node, task, [])
    assert seen == {"query": "Boston"}


def test_evidence_bound_repair_drops_rejected_claims_and_keeps_gap():
    from v2.contracts import Claim, DraftReport, ClaimResult, VerificationReport
    from v2.runtime.assembly import EvidenceBoundRepair
    import asyncio

    draft = DraftReport(sections=["answer"], claims=[
        Claim(text="Grounded 61.", kind="observed", evidence_ids=["ev"]),
        Claim(text="Wrong 62.", kind="observed", evidence_ids=["ev"]),
    ])
    report = VerificationReport(status="repair", claim_results=[
        ClaimResult(claim_index=0, supported=True),
        ClaimResult(claim_index=1, supported=False, reasons=["uncited numeral 62"]),
    ], repair_instructions=["Repair claim 1: uncited numeral 62"])
    result = asyncio.run(EvidenceBoundRepair().repair(None, draft, {}, report))
    assert [claim.text for claim in result.claims] == ["Grounded 61."]
    assert result.gaps == ["Repair claim 1: uncited numeral 62"]


def test_capability_catalog_exposes_real_argument_schemas():
    from v2.runtime.assembly import capability_catalog

    catalog = capability_catalog()
    trajectory = catalog["team_trajectory"]
    assert trajectory["arguments"]["properties"]["team"]
    assert "team" in trajectory["arguments"].get("required", [])
    assert trajectory["arguments"]["properties"]["through_season"]
    assert catalog["web_search"]["arguments"]["properties"]["query"]
    assert catalog["web_fetch"]["arguments"]["properties"]["result_rank"]
    assert catalog["web_fetch"]["arguments"]["properties"]["search_evidence_id"]


def test_build_runtime_wires_configured_checkpoint_store(tmp_path, monkeypatch) -> None:
    from v2.runtime.assembly import build_runtime
    from v2.runtime.policy import ExecutionPolicy

    monkeypatch.setattr("v2.runtime.assembly.ProviderStructuredModel",
                        lambda *args: object())
    policy = ExecutionPolicy.live(ledger_dir=tmp_path / "ledgers").model_copy(
        update={"checkpoint_dir": tmp_path / "checkpoints"})
    runtime, _ = build_runtime(
        provider="inception", model_name="mercury-test", run_id="run",
        policy=policy)
    store = runtime._executor._checkpoint_store
    assert store is not None
    assert store._directory == tmp_path / "checkpoints"
