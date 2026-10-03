from __future__ import annotations

import pytest

from v2.api.routes import _answer_text
from v2.contracts import (
    Claim,
    ClaimKind,
    DraftReport,
    EvidenceOutputBinding,
    Plan,
    PlanNode,
    RunMode,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
)
from v2.runtime import FakeCapability, PlanExecutor, Runtime
from v2.runtime.assembly import MechanicalVerifier

ASSISTS = 880
LEADER_ROWS = [{"PLAYER_ID": 9001, "PLAYER_NAME": "Ada Vega", "AST": ASSISTS}]


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Intake:
    async def understand(self, request: str) -> TaskSpec:
        return TaskSpec(
            goal=request, mode=RunMode.QUICK,
            deliverable="assists leader and total",
            requested_outputs=["AST"])


class Planner:
    async def plan(self, task: TaskSpec) -> Plan:
        return Plan(nodes=[PlanNode(
            id="leaders", description="assists leaderboard",
            capability_hints=["qualified_leaders"])])


class Synthesizer:
    def __init__(self, *claims: Claim) -> None:
        self._claims = claims

    async def synthesize(self, task, evidence) -> DraftReport:
        return DraftReport(sections=["Assists leader"], claims=list(self._claims))


class PassingSemantic:
    async def verify(self, task, draft, evidence) -> VerificationReport:
        return VerificationReport(
            status=VerificationStatus.PASS,
            claim_results=[{"claim_index": index, "supported": True}
                           for index, _claim in enumerate(draft.claims)])


def _assists_claim(declared_value: int) -> Claim:
    return Claim(
        text="Ada Vega led the league with 880 assists.",
        kind=ClaimKind.OBSERVED,
        evidence_ids=["evidence:leaders"],
        output_bindings=[EvidenceOutputBinding(
            requirement_kind="task", requirement_id=None, output_id="AST",
            node_id="leaders", evidence_id="evidence:leaders",
            selector="rows[0].AST",
            value={"kind": "integer", "value": declared_value},
            unit={"kind": "declared", "value": "count"},
            domain="qualified_leaders")])


def _runtime(*claims: Claim) -> Runtime:
    return Runtime(
        intake=Intake(),
        planner=Planner(),
        executor=PlanExecutor({
            "qualified_leaders": FakeCapability("qualified_leaders", LEADER_ROWS)}),
        synthesizer=Synthesizer(*claims),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=PassingSemantic())


@pytest.mark.anyio
async def test_admitted_claim_prose_is_the_published_answer() -> None:
    result = await _runtime(_assists_claim(ASSISTS)).run(
        "Who led the league in assists, and how many?")

    assert [item.status for item in result.output_statuses] == ["complete"]
    text = _answer_text(result)
    assert text.splitlines()[0] == "Ada Vega led the league with 880 assists."
    assert "[player:" not in text
    assert "(count)" not in text


@pytest.mark.anyio
async def test_every_admitted_claim_publishes_in_claim_order() -> None:
    result = await _runtime(
        _assists_claim(ASSISTS),
        Claim(text="That lead is too large to catch.",
              kind=ClaimKind.JUDGMENT),
    ).run("Who led the league in assists, and how many?")

    assert _answer_text(result).splitlines() == [
        "Ada Vega led the league with 880 assists.",
        "That lead is too large to catch."]


@pytest.mark.anyio
async def test_a_claim_whose_binding_admission_refused_publishes_no_prose() -> None:
    result = await _runtime(_assists_claim(ASSISTS + 1)).run(
        "Who led the league in assists, and how many?")

    assert [item.status for item in result.output_statuses] == ["rejected"]
    text = _answer_text(result)
    assert "880" not in text
    assert "AST could not be verified (rejected)." in text
    assert "Some requested outputs could not be published." in text