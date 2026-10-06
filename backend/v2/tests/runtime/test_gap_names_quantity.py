import pytest

from v2.api.routes import _answer_text
from v2.contracts import (
    DraftReport,
    Plan,
    PlanNode,
    RunMode,
    TaskSpec,
)
from v2.runtime import FakeCapability, PlanExecutor, Runtime
from v2.runtime.assembly import MechanicalVerifier
from v2.contracts import VerificationReport, VerificationStatus

@pytest.fixture
def anyio_backend():
    return "asyncio"

class Intake:
    async def understand(self, request: str) -> TaskSpec:
        return TaskSpec(
            goal=request, mode=RunMode.QUICK,
            deliverable="points per game",
            requested_outputs=["PPG"])

class Planner:
    async def plan(self, task: TaskSpec) -> Plan:
        return Plan(nodes=[PlanNode(
            id="scoring", description="season scoring line",
            capability_hints=["player_report"])])

class EmptySynthesizer:
    async def synthesize(self, task, evidence) -> DraftReport:
        return DraftReport(sections=[], claims=[])

class PassingSemantic:
    async def verify(self, task, draft, evidence) -> VerificationReport:
        return VerificationReport(
            status=VerificationStatus.PASS,
            claim_results=[{"claim_index": index, "supported": True}
                           for index, _claim in enumerate(draft.claims)])

@pytest.mark.anyio
async def test_missing_output_gap_names_the_missing_quantity() -> None:
    runtime = Runtime(
        intake=Intake(),
        planner=Planner(),
        executor=PlanExecutor({
            "player_report": FakeCapability("player_report", [{"GP": 0}]),
        }),
        synthesizer=EmptySynthesizer(),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=PassingSemantic())

    result = await runtime.run("How many points per game?")

    assert [item.status for item in result.output_statuses] == ["missing"]
    text = _answer_text(result)
    assert "Some requested outputs could not be verified." not in text
    assert "PPG could not be verified (missing)" in text
    for line in text.splitlines():
        if "could not be verified" in line:
            assert "PPG" in line
    for gap in result.gaps:
        assert "could not be verified" not in gap.message
