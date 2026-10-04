from __future__ import annotations

from datetime import UTC, datetime

import pytest

from v2.api.routes import _answer_text
from v2.contracts import (
    Claim,
    ClaimKind,
    DraftReport,
    EntityRef,
    EvidenceEnvelope,
    EvidenceOutputBinding,
    EvidenceRequirement,
    Plan,
    PlanNode,
    RunMode,
    SeasonRef,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
)
from v2.runtime import FakeCapability, PlanExecutor, Runtime
from v2.runtime.assembly import MechanicalVerifier
from v2.runtime.loop import _verified_claims
from v2.runtime.models import ExecutionResult, RuntimeResult, build_output_statuses

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


_SERIES_NODE = "node_series"
_SERIES_REQUIREMENT = "req_series"

_SERIES_ROWS = {
    "teams": ["BOS", "NYK"],
    "summary": {
        "games": 6,
        "bos_wins": 2,
        "nyk_wins": 4,
        "playoff_meetings": 6,
        "playoff_rounds": "conference semifinals",
        "bos_playoff_wins": 2,
        "nyk_playoff_wins": 4,
    },
    "games": [
        {"game_id": "0042400211", "date": "2025-05-05",
         "matchup": "BOS vs. NYK", "phase": "playoffs",
         "round": "conference semifinals", "winner": "NYK",
         "bos_pts": 105, "nyk_pts": 108},
        {"game_id": "0042400212", "date": "2025-05-07",
         "matchup": "BOS vs. NYK", "phase": "playoffs",
         "round": "conference semifinals", "winner": "NYK",
         "bos_pts": 90, "nyk_pts": 91},
        {"game_id": "0042400213", "date": "2025-05-10",
         "matchup": "BOS @ NYK", "phase": "playoffs",
         "round": "conference semifinals", "winner": "BOS",
         "bos_pts": 115, "nyk_pts": 93},
        {"game_id": "0042400214", "date": "2025-05-12",
         "matchup": "BOS @ NYK", "phase": "playoffs",
         "round": "conference semifinals", "winner": "NYK",
         "bos_pts": 113, "nyk_pts": 121},
        {"game_id": "0042400215", "date": "2025-05-14",
         "matchup": "BOS vs. NYK", "phase": "playoffs",
         "round": "conference semifinals", "winner": "BOS",
         "bos_pts": 127, "nyk_pts": 102},
        {"game_id": "0042400216", "date": "2025-05-16",
         "matchup": "BOS @ NYK", "phase": "playoffs",
         "round": "conference semifinals", "winner": "NYK",
         "bos_pts": 81, "nyk_pts": 119},
    ],
}

_SERIES_TEXTS = [
    "In the 2024-25 season playoffs conference semifinals, "
    "the New York Knicks won the series 4-2 against the Boston Celtics.",
    "On 2025-05-05, the New York Knicks defeated the Boston Celtics "
    "with a score of 108 to 105.",
    "On 2025-05-07, the New York Knicks defeated the Boston Celtics "
    "with a score of 91 to 90.",
    "On 2025-05-10, the Boston Celtics defeated the New York Knicks "
    "with a score of 115 to 93.",
    "On 2025-05-12, the New York Knicks defeated the Boston Celtics "
    "with a score of 121 to 113.",
    "On 2025-05-14, the Boston Celtics defeated the New York Knicks "
    "with a score of 127 to 102.",
    "On 2025-05-16, the New York Knicks defeated the Boston Celtics "
    "with a score of 119 to 81.",
]


def _series_envelope() -> EvidenceEnvelope:
    return EvidenceEnvelope(
        evidence_id="season_series:series-repro",
        capability="season_series",
        source="v1:get_season_series:warehouse team + playoff gamelogs",
        observed_at=datetime.now(UTC),
        season="2024-25",
        task_season_scoped=True,
        entities=[],
        rows=dict(_SERIES_ROWS),
    )


def _series_task() -> TaskSpec:
    return TaskSpec(
        goal="Retrieve the 2024-25 season series results between "
        "the Boston Celtics and the New York Knicks.",
        mode=RunMode.QUICK,
        deliverable="The season series results including winner and scores.",
        requested_outputs=["WINNER", "SCORES"],
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[
            EntityRef(id="BOS", type="team", display_name="Boston Celtics"),
            EntityRef(id="NYK", type="team", display_name="New York Knicks"),
        ],
        requirements=[EvidenceRequirement(
            id=_SERIES_REQUIREMENT,
            description="Retrieve all meetings between Boston Celtics "
            "and New York Knicks in the 2024-25 season",
            capability_options=["season_series"],
            requested_outputs=["WINNER", "SCORES"])],
    )


def _series_claim(text: str, bindings: list, evidence_id: str) -> Claim:
    return Claim(
        text=text,
        kind=ClaimKind.OBSERVED,
        evidence_ids=[evidence_id],
        output_bindings=list(bindings),
    )


def _series_draft(envelope: EvidenceEnvelope) -> DraftReport:
    evidence_id = envelope.evidence_id
    outcome_binding = EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id=_SERIES_REQUIREMENT,
        output_id="WINNER",
        node_id=_SERIES_NODE,
        evidence_id=evidence_id,
        selector="rows.summary.nyk_wins",
        value={"kind": "integer", "value": 4},
        unit={"kind": "unitless"},
        domain="season_series",
    )
    opener_binding = EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id=_SERIES_REQUIREMENT,
        output_id="SCORES",
        node_id=_SERIES_NODE,
        evidence_id=evidence_id,
        selector="rows.games[0].nyk_pts",
        row_selector="rows.games[0]",
        value={"kind": "integer", "value": 108},
        subject_entity_type="team",
        subject_entity_id="NYK",
        subject_selector="rows.games[0].matchup",
        unit={"kind": "declared", "value": "points"},
        domain="season_series",
    )
    claims = [
        _series_claim(_SERIES_TEXTS[0], [outcome_binding], evidence_id),
        _series_claim(_SERIES_TEXTS[1], [opener_binding], evidence_id),
        *(_series_claim(text, [], evidence_id) for text in _SERIES_TEXTS[2:]),
    ]
    return DraftReport(sections=["Season Series Results"], claims=claims)


def test_series_answer_keeps_opener_per_game_lines_and_outcome() -> None:
    envelope = _series_envelope()
    task = _series_task()
    node = PlanNode(
        id=_SERIES_NODE,
        description="Retrieve all meetings between Boston Celtics "
        "and New York Knicks in the 2024-25 season",
        capability_hints=["season_series"],
        covers_requirement_ids=[_SERIES_REQUIREMENT],
        status="complete",
    )
    execution = ExecutionResult(
        plan=Plan(nodes=[node]),
        evidence_by_node={node.id: envelope},
        attempts={node.id: 1},
    )
    draft = _series_draft(envelope)
    verification = VerificationReport(
        status=VerificationStatus.PARTIAL,
        claim_results=[
            {"claim_index": index, "supported": True}
            for index, _claim in enumerate(draft.claims)],
    )
    admitted, binding_gaps = _verified_claims(
        task, execution, draft, verification, {envelope.evidence_id: envelope})

    assert len(admitted) == 7
    assert any(gap.kind.value == "synthesis_incomplete" for gap in binding_gaps)
    result = RuntimeResult(
        task=task,
        execution=execution,
        draft=draft,
        verification=verification,
        verified_claims=admitted,
        gaps=list(binding_gaps),
    )
    lines = _answer_text(result).splitlines()
    assert lines[:7] == _SERIES_TEXTS
    assert "Some requested outputs could not be published." in lines
    assert [item.status for item in result.output_statuses] == [
        "missing"] * 4