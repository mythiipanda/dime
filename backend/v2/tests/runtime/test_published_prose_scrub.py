from __future__ import annotations

from types import SimpleNamespace

import pytest

from v2.api.routes import _answer_text
from v2.contracts import (
    Claim,
    ClaimKind,
    EvidenceOutputBinding,
    OutputFinalStatus,
    Plan,
    PlanNode,
    VerifiedClaim,
)

ASSISTS = 880
PLAYER_ID = "9001"
NODE_ID = "n1"
EVIDENCE_ID = "evidence:leaders"
SELECTOR = "rows[0].AST"
LABEL_LINE = f"AST [player:{PLAYER_ID}] = {ASSISTS} (count)"

PLAIN_PROSE = (
    "Denver's net rating rose 9.4 points per 100 possessions in 2025-26 while "
    "true shooting reached 58.2% over 78 games and 2,941 minutes."
)

LEAKY_PROSE = (
    "Ada Vega led the league with 880 assists per game, from "
    "evidence:leaders and rows[0].AST."
)

RUN_LEAKY_PROSE = (
    "Ada Vega led the league with 880 assists per game from "
    "evidence:leaders at rows.AST."
)

@pytest.fixture
def anyio_backend():
    return "asyncio"

def _binding(*, node: str = NODE_ID, subject: bool = True) -> EvidenceOutputBinding:
    return EvidenceOutputBinding(
        requirement_kind="task", requirement_id=None, output_id="AST",
        node_id=node, evidence_id=EVIDENCE_ID, selector=SELECTOR,
        row_selector="rows[0]" if subject else None,
        subject_entity_type="player" if subject else None,
        subject_entity_id=PLAYER_ID if subject else None,
        subject_selector="rows[0].PLAYER_ID" if subject else None,
        value={"kind": "integer", "value": ASSISTS},
        unit={"kind": "declared", "value": "count"},
        domain="qualified_leaders")

def _claim(text: str) -> Claim:
    return Claim(text=text, kind=ClaimKind.OBSERVED, evidence_ids=[EVIDENCE_ID],
                 output_bindings=[_binding()])

def _judgment(text: str) -> Claim:
    return Claim(text=text, kind=ClaimKind.JUDGMENT)

def _result(*claims: Claim) -> SimpleNamespace:
    verified = [VerifiedClaim(claim_index=index, claim=claim,
                              evidence_ids=list(claim.evidence_ids))
                for index, claim in enumerate(claims)]
    statuses = [
        OutputFinalStatus(
            requirement_kind=binding.requirement_kind,
            requirement_id=binding.requirement_id,
            output_id=binding.output_id, status="complete",
            claim_index=index, binding=binding)
        for index, claim in enumerate(claims)
        for binding in claim.output_bindings]
    return SimpleNamespace(
        output_statuses=statuses, gaps=[], verified_claims=verified,
        execution=SimpleNamespace(evidence=[], plan=Plan(nodes=[PlanNode(
            id=NODE_ID, description="assists leaderboard",
            capability_hints=["qualified_leaders"])])))

def test_claim_prose_citing_its_evidence_and_selector_publishes_without_them() -> None:
    result = _result(_claim(LEAKY_PROSE))

    text = _answer_text(result)
    assert "Ada Vega led the league with 880 assists per game" in text
    assert EVIDENCE_ID not in text
    assert SELECTOR not in text
    assert "AST" not in text

def test_claim_prose_naming_a_capability_and_a_subject_id_publishes_without_them() -> None:
    result = _result(_claim(
        "The qualified_leaders output lists Ada Vega [player:9001] with "
        "880 assists per game."))

    text = _answer_text(result)
    assert "Ada Vega" in text
    assert "880 assists per game" in text
    assert "qualified_leaders" not in text
    assert PLAYER_ID not in text

def test_ordinary_basketball_prose_and_numbers_publish_unchanged() -> None:
    result = _result(_claim(PLAIN_PROSE))

    assert _answer_text(result).splitlines() == [PLAIN_PROSE]

def test_prose_naming_a_node_id_falls_back_to_the_label_lines() -> None:
    result = _result(_claim(
        "Ada Vega led the league with 880 assists per game per n1."))

    assert _answer_text(result) == LABEL_LINE

def test_a_leaky_claim_next_to_clean_prose_neither_leaks_nor_disappears() -> None:
    result = _result(
        _claim("Per n1 the qualified_leaders rows[0].AST player:9001 value "
               "is 880."),
        _claim("That lead is too large to catch."),
        _judgment("Per n1 the projection looks too strong."))

    assert _answer_text(result).splitlines() == [
        LABEL_LINE,
        "That lead is too large to catch.",
    ]

def test_published_prose_names_no_identifier_from_its_own_run() -> None:
    result = _result(
        _claim(LEAKY_PROSE),
        _claim("The qualified_leaders node n1 shows player:9001 at "
               "rows[0].AST."))

    prose = _answer_text(result).splitlines()[0]
    for identifier in (EVIDENCE_ID, SELECTOR, NODE_ID, "qualified_leaders",
                       PLAYER_ID):
        assert identifier not in prose
    assert prose.startswith("Ada Vega led the league with 880 assists")

def test_live_sourced_prose_survives_the_scrub_intact() -> None:
    from v2.contracts import EvidenceEnvelope

    envelope = EvidenceEnvelope(
        evidence_id=EVIDENCE_ID, capability="qualified_leaders",
        source="silver:qualified_leaders:nba_api",
        observed_at="2026-10-03T12:00:00Z", season="2025-26",
        as_of="2026-10-03",
        rows=[{"PLAYER_ID": int(PLAYER_ID), "PLAYER_NAME": "Ada Vega",
               "AST": ASSISTS}],
        source_identity={"kind": "live", "source": "nba_api"})
    result = _result(_claim(LEAKY_PROSE))
    result.execution.evidence = [envelope]

    lines = _answer_text(result).splitlines()
    assert lines[0].startswith("Ada Vega led the league with 880 assists")
    assert lines[-1].startswith("These figures came from the NBA's live feed")

def test_a_claim_that_is_mostly_identifiers_publishes_its_label() -> None:
    result = _result(_claim(
        f"{NODE_ID} {EVIDENCE_ID} {SELECTOR} qualified_leaders"))

    text = _answer_text(result)
    assert text == LABEL_LINE
    assert NODE_ID not in text

def test_an_unbound_leaky_claim_leaves_the_honest_fallback_alone() -> None:
    result = _result(_judgment("Per n1 the outlook looks strong."))
    result.output_statuses = []

    assert _answer_text(result) == (
        "I could not verify a publishable answer from the available data.")

def _leaky_runtime():
    from v2.runtime import FakeCapability, PlanExecutor, Runtime
    from v2.runtime.assembly import MechanicalVerifier

    class Intake:
        async def understand(self, request: str):
            from v2.contracts import RunMode, TaskSpec

            return TaskSpec(goal=request, mode=RunMode.QUICK,
                            deliverable="assists leader",
                            requested_outputs=["AST"])

    class Planner:
        async def plan(self, task):
            from v2.contracts import Plan

            return Plan(nodes=[PlanNode(
                id="leaders", description="assists leaderboard",
                capability_hints=["qualified_leaders"])])

    class Synthesizer:
        async def synthesize(self, task, evidence):
            from v2.contracts import DraftReport

            return DraftReport(sections=["Assists leader"], claims=[
                Claim(text=RUN_LEAKY_PROSE, kind=ClaimKind.OBSERVED,
                      evidence_ids=[EVIDENCE_ID],
                      output_bindings=[_binding(node="leaders",
                                                subject=False)])])

    class PassingSemantic:
        async def verify(self, task, draft, evidence):
            from v2.contracts import VerificationReport, VerificationStatus

            return VerificationReport(
                status=VerificationStatus.PASS,
                claim_results=[{"claim_index": 0, "supported": True}])

    return Runtime(
        intake=Intake(), planner=Planner(),
        executor=PlanExecutor({"qualified_leaders": FakeCapability(
            "qualified_leaders", [{"PLAYER_ID": int(PLAYER_ID),
                                   "PLAYER_NAME": "Ada Vega",
                                   "AST": ASSISTS}])}),
        synthesizer=Synthesizer(), mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=PassingSemantic())

@pytest.mark.anyio
async def test_scrubbed_prose_survives_a_real_run() -> None:
    result = await _leaky_runtime().run(
        "Who led the league in assists, and how many?")

    assert [item.status for item in result.output_statuses] == ["complete"]
    text = _answer_text(result)
    assert "Ada Vega led the league with 880 assists per game" in text
    assert EVIDENCE_ID not in text
    assert SELECTOR not in text