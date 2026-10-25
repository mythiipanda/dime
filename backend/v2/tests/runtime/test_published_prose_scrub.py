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

def _claim(text: str, bindings=None) -> Claim:
    return Claim(text=text, kind=ClaimKind.OBSERVED, evidence_ids=[EVIDENCE_ID],
                 output_bindings=bindings or [_binding()])

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

def test_prose_with_unbound_numbers_falls_back_to_verified_output() -> None:
    result = _result(_claim(PLAIN_PROSE))

    assert _answer_text(result) == LABEL_LINE

def _number_binding(output_id: str, value: str, unit: str) -> EvidenceOutputBinding:
    return EvidenceOutputBinding(
        requirement_kind="task", output_id=output_id, node_id=NODE_ID,
        evidence_id=EVIDENCE_ID, selector=f"rows[0].{output_id}",
        value={"kind": "decimal", "value": value},
        unit={"kind": "declared", "value": unit}, domain="team_summary")

def test_bound_decimal_values_and_exact_task_season_publish_unchanged() -> None:
    prose = (
        "The Thunder posted a 0.5613 effective field-goal percentage "
        "and a 0.1077 turnover percentage in 2025-26.")
    result = _result(_claim(prose, [
        _number_binding("EFG_PCT", "0.5613", "percent"),
        _number_binding("TOV_PCT", "0.1077", "percent"),
    ]))
    result.task = SimpleNamespace(season=SimpleNamespace(value="2025-26"))

    assert _answer_text(result).splitlines() == [prose]

def test_parenthesized_output_label_drops_without_a_placeholder() -> None:
    result = _result(_claim(
        "The effective field-goal percentage (EFG_PCT) reached 0.5613.",
        [_number_binding("EFG_PCT", "0.5613", "percent")]))

    text = _answer_text(result)
    assert "(EFG_PCT)" not in text
    assert "the data" not in text
    assert "0.5613" in text

def test_prose_naming_a_node_id_falls_back_to_the_label_lines() -> None:
    result = _result(_claim(
        "Ada Vega led the league with 880 assists per game per n1."))

    assert _answer_text(result) == LABEL_LINE

def test_team_id_label_form_scrubs_and_keeps_identity_and_season() -> None:
    team_id = "1610612738"

    def team_binding(output_id: str, value: int, unit: str) -> EvidenceOutputBinding:
        return EvidenceOutputBinding(
            requirement_kind="task", requirement_id=None, output_id=output_id,
            node_id=NODE_ID, evidence_id=EVIDENCE_ID,
            selector=f"rows[0].{output_id}", row_selector="rows[0]",
            subject_entity_type="team", subject_entity_id=team_id,
            subject_selector="rows[0].TEAM_ID",
            value={"kind": "integer", "value": value},
            unit={"kind": "declared", "value": unit}, domain="team_summary")

    result = _result(_claim(
        "The Boston Celtics (team ID 1610612738) had 82 games and "
        "9,534 points in 2024-25.",
        [team_binding("GAMES", 82, "count"),
         team_binding("PTS", 9534, "points")]))
    result.task = SimpleNamespace(season=SimpleNamespace(value="2024-25"))

    text = _answer_text(result)
    assert text == (
        "The Boston Celtics had 82 games and 9,534 points in 2024-25.")
    assert team_id not in text

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

def test_source_label_survives_only_when_bound_warehouse_metadata_names_it() -> None:
    from v2.contracts import ClaimSource, EvidenceEnvelope

    prose = "Boston had 880 assists in 2024-25 from silver_hist_gamelogs."
    result = _result(_claim(prose))
    result.task = SimpleNamespace(season=SimpleNamespace(value="2024-25"))
    envelope = EvidenceEnvelope(
        evidence_id=EVIDENCE_ID, capability="team_season_summary",
        source="v1:get_team_season_summary:warehouse:silver_hist_gamelogs",
        observed_at="2026-10-24T00:00:00Z", season="2024-25",
        rows={"AST": ASSISTS},
        source_identity={"kind": "warehouse", "warehouse_id": "configured-runtime",
                         "sha256": "a" * 64})
    result.execution.evidence = [envelope]
    result.verified_claims = [result.verified_claims[0].model_copy(update={
        "sources": [ClaimSource(
            evidence_id=EVIDENCE_ID, source=envelope.source,
            capability=envelope.capability)]})]

    text = _answer_text(result)
    assert "silver_hist_gamelogs" in text
    assert EVIDENCE_ID not in text
    assert "team_season_summary" not in text
    assert "from the data" not in text

def test_bound_source_label_remains_when_unbound_number_withholds_prose() -> None:
    from v2.contracts import ClaimSource, EvidenceEnvelope

    envelope = EvidenceEnvelope(
        evidence_id=EVIDENCE_ID, capability="team_season_summary",
        source="v1:get_team_season_summary:warehouse:silver_hist_gamelogs",
        observed_at="2026-10-24T00:00:00Z", season="2024-25",
        rows={"AST": ASSISTS},
        source_identity={"kind": "warehouse", "warehouse_id": "configured-runtime",
                         "sha256": "a" * 64})
    claim = _claim(
        "Boston had 2024 wins in 2024-25 from silver_hist_gamelogs.")
    result = _result(claim)
    result.task = SimpleNamespace(season=SimpleNamespace(value="2024-25"))
    result.execution.evidence = [envelope]
    result.verified_claims = [result.verified_claims[0].model_copy(update={
        "sources": [ClaimSource(
            evidence_id=EVIDENCE_ID, source=envelope.source,
            capability=envelope.capability)]})]

    assert _answer_text(result).splitlines() == [
        LABEL_LINE, "Source: silver_hist_gamelogs."]

def test_source_tool_name_must_match_registered_capability() -> None:
    from v2.contracts import ClaimSource, EvidenceEnvelope

    envelope = EvidenceEnvelope(
        evidence_id=EVIDENCE_ID, capability="team_season_summary",
        source="v1:unregistered_summary_tool:warehouse:silver_hist_gamelogs",
        observed_at="2026-10-24T00:00:00Z", season="2024-25",
        rows={"AST": ASSISTS},
        source_identity={"kind": "warehouse", "warehouse_id": "configured-runtime",
                         "sha256": "a" * 64})
    result = _result(_claim("Boston had 880 assists in 2024-25."))
    result.task = SimpleNamespace(season=SimpleNamespace(value="2024-25"))
    result.execution.evidence = [envelope]
    result.verified_claims = [result.verified_claims[0].model_copy(update={
        "sources": [ClaimSource(
            evidence_id=EVIDENCE_ID, source=envelope.source,
            capability=envelope.capability)]})]

    assert "Source:" not in _answer_text(result)


def test_unbound_table_like_identifier_does_not_use_source_exception() -> None:
    prose = "Boston had 880 assists from silver_private_table."
    result = _result(_claim(prose))

    text = _answer_text(result)
    assert "silver_private_table" not in text
    assert "880 assists" in text


def test_repeated_scrub_placeholders_are_removed() -> None:
    prose = "Boston had 880 assists (the data; the data, the data)."
    result = _result(_claim(prose))

    text = _answer_text(result)
    assert text == "Boston had 880 assists."
    assert "the data" not in text


@pytest.mark.parametrize("shown,expected", [
    ("116.26829268292683", "116.26829268292683"),
    ("116.2", "116.26829268292683"),
])
def test_calculation_prose_requires_exact_admitted_number(shown, expected) -> None:
    from v2.contracts import (
        CalculationOutputBinding,
        DeclaredCalculation,
        DeclaredCalculationInput,
    )

    calculation = DeclaredCalculation(
        calculation_id="mean_ppg_calc", requirement_id="mean_ppg",
        operation="divide", inputs=[
            DeclaredCalculationInput(evidence_id=EVIDENCE_ID,
                                     path="rows[0].PTS"),
            DeclaredCalculationInput(evidence_id=EVIDENCE_ID,
                                     path="rows[0].GAMES"),
        ], result="116.26829268292683", unit="points per game")
    calculation_binding = CalculationOutputBinding(
        requirement_id="mean_ppg", output_id="MEAN_PPG",
        calculation_id="mean_ppg_calc")
    points_binding = _number_binding("PTS", "9534", "points")
    games_binding = _number_binding("GAMES", "82", "count")
    claim = Claim(
        text=f"Mean points per game = 9,534 / 82 = {shown}.",
        kind=ClaimKind.DERIVED, evidence_ids=[EVIDENCE_ID],
        calculation_id="mean_ppg_calc",
        output_bindings=[points_binding, games_binding, calculation_binding])
    result = _result(claim)
    result.draft = SimpleNamespace(calculations=[calculation])
    result.task = SimpleNamespace(season=SimpleNamespace(value="2024-25"))
    from v2.api.routes import _claim_numbers_are_admitted
    assert _claim_numbers_are_admitted(
        result, result.verified_claims[0], None) is (shown == expected)

    text = _answer_text(result)
    if shown == expected:
        assert text == claim.text
    else:
        assert text.splitlines() == [
            "PTS = 9534 (points)",
            "GAMES = 82 (count)",
            f"MEAN_PPG = {expected} (points per game)",
        ]
        assert f"= {shown}." not in text


def test_derived_claim_arithmetic_operands_publish_from_calculation_inputs() -> None:
    from v2.contracts import (
        CalculationOutputBinding,
        DeclaredCalculation,
        DeclaredCalculationInput,
        EvidenceEnvelope,
    )

    evidence_id = "team_season_summary:3ae6a6161d11237a"
    calculation = DeclaredCalculation(
        calculation_id="mean_ppg", requirement_id="mean_ppg",
        operation="divide", inputs=[
            DeclaredCalculationInput(evidence_id=evidence_id,
                                     path="rows[0].PTS"),
            DeclaredCalculationInput(evidence_id=evidence_id,
                                     path="rows[0].GAMES"),
        ], result="116.26829268292683", unit="per_game")
    calculation_binding = CalculationOutputBinding(
        requirement_id="mean_ppg", output_id="MEAN_PPG",
        calculation_id="mean_ppg")
    claim = Claim(
        text="Mean points per game is 116.26829268292683, computed as "
             "9,534 total points divided by 82 games.",
        kind=ClaimKind.DERIVED, evidence_ids=[evidence_id],
        calculation_id="mean_ppg", output_bindings=[calculation_binding])
    result = _result(claim)
    result.draft = SimpleNamespace(calculations=[calculation])
    result.execution.evidence = [EvidenceEnvelope(
        evidence_id=evidence_id, capability="team_season_summary",
        source="v1:get_team_season_summary:warehouse:silver_hist_gamelogs",
        observed_at="2026-10-25T05:11:40Z", season="2024-25",
        rows=[{"GAMES": 82, "PTS": 9534,
               "PPG": 116.26829268292683}],
        units={"GAMES": "count", "PTS": "points", "PPG": "per_game"})]

    assert _answer_text(result) == claim.text


def test_unbound_four_digit_number_is_not_treated_as_verified_season() -> None:
    prose = "Boston recorded 2024 wins during the 2024-25 season."
    result = _result(_claim(prose, [_number_binding("MEAN_PPG", "116.2", "points per game")]))
    result.task = SimpleNamespace(season=SimpleNamespace(value="2024-25"))

    assert _answer_text(result) == "MEAN_PPG = 116.2 (points per game)"
