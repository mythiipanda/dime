from datetime import UTC, datetime

from v2.adapters.capabilities import CAPABILITIES
from v2.adapters.core import build_envelope
from v2.adapters.models import (_backfill_open_question_outputs,
                                _drop_unresolvable_requested_outputs,
                                _finalize_requested_outputs)
from v2.contracts import (
    CalculationOutputBinding,
    CalculationRequirement,
    Claim,
    ClaimSource,
    DeclaredCalculation,
    DeclaredCalculationInput,
    DraftReport,
    EntityRef,
    EvidenceOutputBinding,
    EvidenceRequirement,
    Plan,
    PlanNode,
    SeasonRef,
    TaskSpec,
    VerifiedClaim,
)
from v2.runtime.models import (
    ExecutionResult,
    admit_verified_claim_bindings,
    build_output_statuses,
    propagate_evidence_to_task,
)

_NODE_ID = "node_team_four_factors"
_REQUIREMENT_ID = "req_team_four_factors"
_OUTPUTS = ["EFG_PCT", "FT_RATE", "ORB_PCT", "TOV_PCT"]

def _open_task():
    return TaskSpec(
        goal="What are the Thunder four factors in the 2025-26 season?",
        mode="quick",
        deliverable="The Oklahoma City Thunder four-factor profile for 2025-26.",
        season=SeasonRef(value="2025-26", source="user", confidence=1.0),
        entities=[EntityRef(id="1610612760", type="team",
                            display_name="Oklahoma City Thunder")],
        required_evidence=["team_four_factors"],
        requirements=[EvidenceRequirement(
            id=_REQUIREMENT_ID,
            description="Thunder four factors for 2025-26",
            capability_options=["team_four_factors"],
        )],
    )

def test_backfill_fills_empty_authority_from_capability_catalog():
    filled = _backfill_open_question_outputs(_open_task())
    assert sorted(filled.requested_outputs) == sorted(_OUTPUTS)
    assert sorted(filled.requirements[0].requested_outputs) == sorted(_OUTPUTS)

def test_backfill_leaves_named_authority_untouched():
    named = _open_task().model_copy(update={
        "requested_outputs": ["EFG_PCT"],
        "requirements": [_open_task().requirements[0].model_copy(
            update={"requested_outputs": ["EFG_PCT"]})],
    })
    assert _backfill_open_question_outputs(named) == named

def test_backfill_skips_requirements_without_catalog_options():
    task = _open_task().model_copy(update={
        "requirements": [_open_task().requirements[0].model_copy(
            update={"capability_options": ["not_a_capability"]})],
    })
    assert _backfill_open_question_outputs(task) == task

def _envelope():
    return build_envelope(
        CAPABILITIES["team_four_factors"],
        {"season": "2025-26"},
        {"ok": True, "rows": [{
            "TEAM_ID": 1610612760,
            "TEAM_NAME": "Oklahoma City Thunder",
            "SEASON": "2025-26",
            "EFG_PCT": 0.557,
            "FT_RATE": 0.181,
            "ORB_PCT": 0.264,
            "TOV_PCT": 0.118,
        }], "meta": {
            "source": "warehouse",
            "season": "2025-26",
            "warehouse_id": "frozen-eval",
            "warehouse_sha256": "a" * 64,
        }},
        entities=None,
        observed_at=datetime.now(UTC),
    )

def _bindings(envelope):
    values = {"EFG_PCT": 0.557, "FT_RATE": 0.181,
              "ORB_PCT": 0.264, "TOV_PCT": 0.118}
    return [
        EvidenceOutputBinding(
            requirement_kind="task",
            requirement_id=None,
            output_id=output_id,
            node_id=_NODE_ID,
            evidence_id=envelope.evidence_id,
            selector=f"rows[0].{output_id}",
            row_selector="rows[0]",
            value={"kind": "float", "value": values[output_id]},
            subject_entity_type="team",
            subject_entity_id="1610612760",
            subject_selector="rows[0].TEAM_ID",
            unit={"kind": "unitless"},
            domain="team_four_factors",
        )
        for output_id in _OUTPUTS
    ]

def test_unresolvable_intake_outputs_drop_before_planning():
    task = _open_task().model_copy(update={
        "requested_outputs": ["EFG_PCT", "OREB_PCT", "DREB_PCT"],
        "requirements": [_open_task().requirements[0].model_copy(
            update={"requested_outputs": ["EFG_PCT", "OREB_PCT", "DREB_PCT"]})],
    })
    repaired = _drop_unresolvable_requested_outputs(task)
    assert repaired.requested_outputs == ["EFG_PCT"]
    assert repaired.requirements[0].requested_outputs == ["EFG_PCT"]

def test_drop_keeps_identity_and_calculation_outputs():
    task = _open_task().model_copy(update={
        "requested_outputs": ["TEAM_NAME", "OREB_PCT", "FOUR_FACTOR_MARGIN"],
        "calculation_requirements": [CalculationRequirement(
            id="margin",
            description="factor margin",
            requested_outputs=["FOUR_FACTOR_MARGIN"],
        )],
        "requirements": [_open_task().requirements[0].model_copy(
            update={"requested_outputs": ["TEAM_NAME", "OREB_PCT"]})],
    })
    repaired = _drop_unresolvable_requested_outputs(task)
    assert repaired.requested_outputs == ["TEAM_NAME", "FOUR_FACTOR_MARGIN"]
    assert repaired.requirements[0].requested_outputs == ["TEAM_NAME"]

def test_drop_leaves_resolvable_authority_untouched():
    task = _open_task().model_copy(update={
        "requested_outputs": ["EFG_PCT", "TOV_PCT"],
        "requirements": [_open_task().requirements[0].model_copy(
            update={"requested_outputs": ["EFG_PCT", "TOV_PCT"]})],
    })
    assert _drop_unresolvable_requested_outputs(task) == task

def test_structural_capability_outputs_survive_the_drop():
    task = _open_task().model_copy(update={
        "requested_outputs": ["WINNER", "SCORES"],
        "required_evidence": ["season_series"],
        "requirements": [EvidenceRequirement(
            id="series",
            description="Celtics Knicks 2024-25 series",
            capability_options=["season_series"],
            requested_outputs=["WINNER", "SCORES"],
        )],
    })
    assert _drop_unresolvable_requested_outputs(task) == task

def test_backfilled_authority_admits_claims_and_completes_every_status():
    task = _backfill_open_question_outputs(_open_task())
    envelope = _envelope()
    node = PlanNode(
        id=_NODE_ID,
        description="Thunder four factors for 2025-26",
        capability_hints=["team_four_factors"],
        covers_requirement_ids=[_REQUIREMENT_ID],
        arguments={},
        status="complete",
    )
    execution = ExecutionResult(
        plan=Plan(nodes=[node]),
        evidence_by_node={_NODE_ID: envelope},
        attempts={_NODE_ID: 1},
    )
    bindings = _bindings(envelope)
    claim = Claim(
        text="The Thunder posted a 0.557 effective field-goal percentage in 2025-26.",
        kind="observed",
        evidence_ids=[envelope.evidence_id],
        output_bindings=bindings,
    )
    draft = DraftReport(sections=["Four factors"], claims=[claim])
    verified = VerifiedClaim(
        claim_index=0,
        claim=claim,
        evidence_ids=[envelope.evidence_id],
        sources=[ClaimSource(
            evidence_id=envelope.evidence_id,
            source=envelope.source,
            capability=envelope.capability,
            observed_at=envelope.observed_at,
        )],
        output_bindings=bindings,
    )
    admitted = admit_verified_claim_bindings(task, execution, draft, verified)
    assert sorted(item.output_id for item in admitted.output_bindings) == sorted(_OUTPUTS)
    mirrored = propagate_evidence_to_task(task, execution, draft, [admitted])
    rows = build_output_statuses(task, mirrored, [])
    assert len(rows) == 8
    assert {row.status for row in rows} == {"complete"}

def test_a_metric_id_no_capability_can_serve_is_dropped() -> None:
    from v2.adapters.models import _drop_unresolvable_requested_outputs
    from v2.contracts import EvidenceRequirement, TaskSpec

    task = TaskSpec(
        goal="mvp",
        mode="quick",
        deliverable="winner and share",
        requirements=[EvidenceRequirement(
            id="award",
            description="official MVP result",
            capability_options=["award_results"],
            requested_outputs=["PLAYER", "AWARD_SHARE"],
            metric_ids=["MVP", "AWARD_SHARE"],
        )],
    )

    result = _drop_unresolvable_requested_outputs(task)

    assert result.requirements[0].metric_ids == ["AWARD_SHARE"]

def test_an_open_vocabulary_capability_keeps_the_metric_id() -> None:
    from v2.adapters.models import _drop_unresolvable_requested_outputs
    from v2.contracts import EvidenceRequirement, TaskSpec

    task = TaskSpec(
        goal="rates",
        mode="deep_dive",
        deliverable="table",
        requirements=[EvidenceRequirement(
            id="rates",
            description="agent-written rate query",
            capability_options=["sql_exec"],
            requested_outputs=["TS_PCT"],
            metric_ids=["TS_PCT"],
        )],
    )

    assert _drop_unresolvable_requested_outputs(task) == task

_CELTICS_NODE = "celtics_2024_25_regular_summary"
_CELTICS_REQUIREMENT = "celtics_2024_25_regular_summary"
_CELTICS_ROW = {
    "TEAM_ID": 1610612738,
    "TEAM_NAME": "Boston Celtics",
    "SEASON": "2024-25",
    "PERIOD_SCOPE": "regular_season",
    "GAMES": 82,
    "WINS": 61,
    "LOSSES": 21,
    "PTS": 9534,
    "PPG": 116.26829268292683,
}

def _captured_task():
    return TaskSpec(
        goal=(
            "For the Boston Celtics in the 2024-25 regular season only, "
            "report games, wins, losses, total points scored, and mean "
            "points per game. Use historical team game logs, exclude "
            "playoffs, and cite the table, season filter, and source "
            "evidence. Show the arithmetic."
        ),
        mode="quick",
        deliverable="Boston Celtics 2024-25 regular-season summary",
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[EntityRef(id="1610612738", type="team",
                            display_name="Boston Celtics")],
        required_evidence=["entity_resolution", "team_season_summary"],
        requirements=[
            EvidenceRequirement(
                id="resolve_celtics",
                description="Resolve the Celtics to the canonical team.",
                capability_options=["entity_resolution"],
            ),
            EvidenceRequirement(
                id=_CELTICS_REQUIREMENT,
                description="Celtics 2024-25 regular-season summary",
                capability_options=["team_season_summary"],
                capability_arguments={"period_scope": "regular_season"},
            ),
        ],
        calculation_requirements=[
            CalculationRequirement(
                id="mean_ppg",
                description=("Compute mean points per game as total points "
                             "scored divided by games played."),
            ),
            CalculationRequirement(
                id="games_check",
                description="Verify that wins plus losses equals games.",
            ),
        ],
    )

def _captured_envelope():
    return build_envelope(
        CAPABILITIES["team_season_summary"],
        {"team_id": 1610612738, "season": "2024-25",
         "period_scope": "regular_season"},
        {"ok": True, "rows": [dict(_CELTICS_ROW)], "meta": {
            "source": "warehouse",
            "season": "2024-25",
            "warehouse_id": "frozen-eval",
            "warehouse_sha256": "a" * 64,
        }},
        entities=None,
        observed_at=datetime.now(UTC),
    )

def _celtics_binding(envelope, output_id, selector, value, kind, unit):
    return EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id=_CELTICS_REQUIREMENT,
        output_id=output_id,
        node_id=_CELTICS_NODE,
        evidence_id=envelope.evidence_id,
        selector=selector,
        row_selector="rows[0]",
        value={"kind": kind, "value": value},
        subject_entity_type="team",
        subject_entity_id="1610612738",
        subject_selector="rows[0].TEAM_ID",
        unit={"kind": "declared", "value": unit},
        domain="team_season_summary",
    )

def test_captured_intake_aligns_calculation_authority_after_backfill():
    task = _finalize_requested_outputs(_captured_task())
    calculations = {item.id: item for item in task.calculation_requirements}
    assert calculations["mean_ppg"].requested_outputs == ["MEAN_PPG"]
    assert calculations["games_check"].requested_outputs == []
    requirement = task.requirements[1]
    for output_id in ("GAMES", "WINS", "LOSSES", "PTS", "PPG",
                      "TOTAL_POINTS", "POINTS_PER_GAME", "MEAN_PPG"):
        assert output_id in requirement.requested_outputs
        assert output_id in task.requested_outputs

def test_captured_mean_ppg_keeps_calculation_authority_and_alias_outputs():
    task = _finalize_requested_outputs(_captured_task())
    envelope = _captured_envelope()
    node = PlanNode(
        id=_CELTICS_NODE,
        description="Celtics 2024-25 regular-season summary",
        capability_hints=["team_season_summary"],
        covers_requirement_ids=[_CELTICS_REQUIREMENT],
        arguments={"team_id": 1610612738, "season": "2024-25",
                   "period_scope": "regular_season"},
        status="complete",
    )
    execution = ExecutionResult(
        plan=Plan(nodes=[node]),
        evidence_by_node={_CELTICS_NODE: envelope},
        attempts={_CELTICS_NODE: 1},
    )
    observed = [
        _celtics_binding(envelope, "GAMES", "rows[0].GAMES", 82,
                         "integer", "count"),
        _celtics_binding(envelope, "WINS", "rows[0].WINS", 61,
                         "integer", "count"),
        _celtics_binding(envelope, "LOSSES", "rows[0].LOSSES", 21,
                         "integer", "count"),
        _celtics_binding(envelope, "PTS", "rows[0].PTS", 9534,
                         "integer", "points"),
        _celtics_binding(envelope, "TOTAL_POINTS", "rows[0].PTS", 9534,
                         "integer", "points"),
        _celtics_binding(envelope, "PPG", "rows[0].PPG",
                         116.26829268292683, "float", "per_game"),
        _celtics_binding(envelope, "POINTS_PER_GAME", "rows[0].PPG",
                         116.26829268292683, "float", "per_game"),
    ]
    mean = _celtics_binding(envelope, "MEAN_PPG", "rows[0].PPG",
                            116.26829268292683, "float", "per_game")
    calculations = [
        DeclaredCalculation(
            calculation_id="mean_ppg",
            requirement_id="mean_ppg",
            operation="divide",
            inputs=[DeclaredCalculationInput(
                        evidence_id=envelope.evidence_id,
                        path="rows[0].PTS"),
                    DeclaredCalculationInput(
                        evidence_id=envelope.evidence_id,
                        path="rows[0].GAMES")],
            result="116.26829268292683",
            unit="per_game",
        ),
        DeclaredCalculation(
            calculation_id="games_check",
            requirement_id="games_check",
            operation="add",
            inputs=[DeclaredCalculationInput(
                        evidence_id=envelope.evidence_id,
                        path="rows[0].WINS"),
                    DeclaredCalculationInput(
                        evidence_id=envelope.evidence_id,
                        path="rows[0].LOSSES")],
            result="82",
            unit="count",
        ),
    ]
    claims = [
        Claim(
            text=("The Celtics played 82 games, won 61, lost 21, and "
                  "scored 9,534 points in 2024-25."),
            kind="observed",
            evidence_ids=[envelope.evidence_id],
            output_bindings=observed,
        ),
        Claim(
            text=("The Celtics averaged 116.26829268292683 points per "
                  "game: 9,534 divided by 82."),
            kind="derived",
            evidence_ids=[envelope.evidence_id],
            calculation_id="mean_ppg",
            output_bindings=[
                CalculationOutputBinding(
                    requirement_kind="calculation",
                    requirement_id="mean_ppg",
                    output_id="MEAN_PPG",
                    calculation_id="mean_ppg",
                ),
                mean,
            ],
        ),
    ]
    draft = DraftReport(sections=["Celtics summary"], claims=claims,
                        calculations=calculations)
    admitted = [
        admit_verified_claim_bindings(
            task, execution, draft,
            VerifiedClaim(
                claim_index=index,
                claim=claim,
                evidence_ids=[envelope.evidence_id],
                sources=[ClaimSource(
                    evidence_id=envelope.evidence_id,
                    source=envelope.source,
                    capability=envelope.capability,
                    observed_at=envelope.observed_at,
                )],
                output_bindings=claim.output_bindings,
            ),
        )
        for index, claim in enumerate(claims)
    ]
    assert sorted(item.output_id for item in admitted[1].output_bindings) == [
        "MEAN_PPG", "MEAN_PPG"]
    mirrored = propagate_evidence_to_task(task, execution, draft, admitted)
    rows = build_output_statuses(task, mirrored, [])
    assert {row.status for row in rows} == {"complete"}
    assert all(row.status == "complete"
               for row in rows if row.output_id == "MEAN_PPG")
    published = {row.output_id for row in rows}
    assert {"GAMES", "WINS", "LOSSES", "PTS", "TOTAL_POINTS", "PPG",
            "POINTS_PER_GAME", "MEAN_PPG"} <= published
    assert envelope.rows[0]["SEASON"] == "2024-25"
    assert envelope.rows[0]["TEAM_ID"] == 1610612738
    assert envelope.rows[0]["PTS"] == 9534
    assert "season completeness is unverified" in envelope.coverage
    assert abs(envelope.rows[0]["PTS"] / envelope.rows[0]["GAMES"]
               - 116.26829268292683) < 1e-12