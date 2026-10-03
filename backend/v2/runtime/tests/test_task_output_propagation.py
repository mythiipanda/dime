from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from v2.adapters.capabilities import CAPABILITIES
from v2.adapters.core import build_envelope
from v2.api.routes import _answer_text, _public_output_status
from v2.contracts import (
    Claim,
    ClaimSource,
    DraftReport,
    EntityRef,
    EvidenceOutputBinding,
    EvidenceRequirement,
    Plan,
    PlanNode,
    SeasonRef,
    TaskSpec,
    VerificationReport,
    VerifiedClaim,
)
from v2.runtime.loop import _verified_claims
from v2.runtime.models import (
    ExecutionResult,
    admit_verified_claim_bindings,
    build_output_statuses,
)


_NODE_ID = "leaders"


def _leader_rows():
    return [
        {
            "PLAYER_ID": 1629027,
            "PLAYER_NAME": "Trae Young",
            "GP": 76,
            "MIN": 2700,
            "AST": 880,
            "PTS": 1500,
        },
        {
            "PLAYER_ID": 1628369,
            "PLAYER_NAME": "Nikola Jokic",
            "GP": 74,
            "MIN": 2600,
            "AST": 700,
            "PTS": 1900,
        },
    ]


def _warehouse_meta():
    return {
        "source": "warehouse",
        "season": "2024-25",
        "warehouse_id": "frozen-eval",
        "warehouse_sha256": "a" * 64,
    }


def _envelope(rows=None):
    return build_envelope(
        CAPABILITIES["qualified_leaders"],
        {"season": "2024-25", "stat_category": "AST"},
        {"ok": True, "rows": rows if rows is not None else _leader_rows(),
         "meta": dict(_warehouse_meta())},
        entities=None,
        observed_at=datetime.now(UTC),
    )


def _trae():
    return EntityRef(id="1629027", type="player", display_name="Trae Young")


def _jokic():
    return EntityRef(id="1628369", type="player", display_name="Nikola Jokic")


def _requirement(requirement_id, outputs):
    return EvidenceRequirement(
        id=requirement_id,
        description="2024-25 assists leaderboard",
        capability_options=["qualified_leaders"],
        requested_outputs=list(outputs),
    )


def _task(entities, requirements, outputs):
    return TaskSpec(
        goal="Who led the NBA in assists in the 2024-25 season, and how many?",
        mode="quick",
        deliverable="Assists leader and total assists",
        requested_outputs=list(outputs),
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=list(entities),
        requirements=list(requirements),
    )


def _binding(output_id, value, requirement_id, row, subject_id, subject_name,
             node_id=_NODE_ID):
    selector = f"rows[{row}].{output_id}"
    if output_id == "PLAYER_NAME":
        unit = {"kind": "unitless"}
        declared = {"kind": "string", "value": value}
    else:
        unit = {"kind": "declared", "value": "count"}
        declared = {"kind": "integer", "value": value}
    return EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id=requirement_id,
        output_id=output_id,
        node_id=node_id,
        evidence_id="placeholder",
        selector=selector,
        row_selector=f"rows[{row}]",
        value=declared,
        subject_entity_type="player",
        subject_entity_id=subject_id,
        subject_selector=f"rows[{row}].PLAYER_ID",
        unit=unit,
        domain="qualified_leaders",
    )


def _q1_bindings(envelope, node_id=_NODE_ID):
    return [
        binding.model_copy(update={"evidence_id": envelope.evidence_id})
        for binding in (
            _binding("PLAYER_NAME", "Trae Young", "player_assists_leader",
                     0, "1629027", "Trae Young", node_id=node_id),
            _binding("AST", 880, "player_assists_leader",
                     0, "1629027", "Trae Young", node_id=node_id),
        )
    ]


def _node(covers):
    return PlanNode(
        id=_NODE_ID,
        description="2024-25 assists leaderboard",
        capability_hints=["qualified_leaders"],
        covers_requirement_ids=list(covers),
        status="complete",
    )


def _execution(envelope, node):
    return ExecutionResult(
        plan=Plan(nodes=[node]),
        evidence_by_node={node.id: envelope},
        attempts={node.id: 1},
    )


def _report():
    return VerificationReport(
        status="pass",
        claim_results=[{"claim_index": 0, "supported": True, "reasons": []}],
    )


def _claim(bindings, evidence_id):
    return Claim(
        text="Trae Young led the NBA with 880 assists in 2024-25.",
        kind="observed",
        evidence_ids=[evidence_id],
        output_bindings=list(bindings),
    )


def _admitted(task, execution, envelope, bindings):
    claim = _claim(bindings, envelope.evidence_id)
    draft = DraftReport(sections=["Assists leader"], claims=[claim])
    evidence = {envelope.evidence_id: envelope}
    claims, gaps = _verified_claims(task, execution, draft, _report(), evidence)
    statuses = build_output_statuses(task, claims, gaps)
    return claims, gaps, {
        (row.requirement_kind, row.requirement_id, row.output_id): row
        for row in statuses
    }


def _answer(task, execution, envelope, bindings):
    claims, gaps, by_key = _admitted(task, execution, envelope, bindings)
    result = SimpleNamespace(
        output_statuses=list(by_key.values()), gaps=gaps, execution=execution,
        verified_claims=claims,
        draft=DraftReport(sections=["Assists leader"], claims=[]))
    return _answer_text(result)


def test_evidence_only_q1_bindings_own_task_outputs():
    envelope = _envelope()
    task = _task([_trae()], [_requirement("player_assists_leader",
                                         ["PLAYER_NAME", "AST"])],
                 ["PLAYER_NAME", "AST"])
    bindings = _q1_bindings(envelope)
    _, _, by_key = _admitted(
        task, _execution(envelope, _node(["player_assists_leader"])),
        envelope, bindings)
    assert by_key[("task", None, "PLAYER_NAME")].status == "complete"
    assert by_key[("task", None, "PLAYER_NAME")].binding.value.value == "Trae Young"
    assert by_key[("task", None, "AST")].status == "complete"
    assert by_key[("task", None, "AST")].binding.value.value == 880


def test_binding_naming_a_requirement_instead_of_the_plan_node_still_owns_task_outputs():
    envelope = _envelope()
    task = _task([], [_requirement("player_assists_leader",
                                   ["PLAYER_NAME", "AST"])],
                 ["PLAYER_NAME", "AST"])
    execution = _execution(envelope, _node(["player_assists_leader"]))
    bindings = _q1_bindings(envelope, node_id="player_assists_leader")

    assert _answer(task, execution, envelope, bindings).splitlines() == [
        "Trae Young led the NBA with 880 assists in 2024-25."]


def test_league_scoped_task_outputs_own_the_leader_the_envelope_carries():
    envelope = _envelope()
    task = _task([EntityRef(id="nba", type="league", display_name="NBA")],
                 [_requirement("player_assists_leader",
                               ["PLAYER_NAME", "AST"])],
                 ["PLAYER_NAME", "AST"])
    execution = _execution(envelope, _node(["player_assists_leader"]))
    bindings = _q1_bindings(envelope)
    _, _, by_key = _admitted(task, execution, envelope, bindings)
    assert by_key[("evidence", "player_assists_leader",
                   "PLAYER_NAME")].status == "complete"
    assert by_key[("task", None, "PLAYER_NAME")].status == "complete"
    assert by_key[("task", None, "AST")].status == "complete"
    assert _answer(task, execution, envelope, bindings).splitlines() == [
        "Trae Young led the NBA with 880 assists in 2024-25."]


def test_competing_evidence_subjects_leave_task_output_missing():
    envelope = _envelope()
    task = _task([_trae(), _jokic()],
                 [_requirement("leaders_a", ["PLAYER_NAME"]),
                  _requirement("leaders_b", ["PLAYER_NAME"])],
                 ["PLAYER_NAME"])
    bindings = [
        binding.model_copy(update={"evidence_id": envelope.evidence_id})
        for binding in (
            _binding("PLAYER_NAME", "Trae Young", "leaders_a",
                     0, "1629027", "Trae Young"),
            _binding("PLAYER_NAME", "Nikola Jokic", "leaders_b",
                     1, "1628369", "Nikola Jokic"),
        )
    ]
    _, _, by_key = _admitted(
        task, _execution(envelope, _node(["leaders_a", "leaders_b"])),
        envelope, bindings)
    assert by_key[("evidence", "leaders_a", "PLAYER_NAME")].status == "complete"
    assert by_key[("evidence", "leaders_b", "PLAYER_NAME")].status == "complete"
    assert by_key[("task", None, "PLAYER_NAME")].status == "missing"


def test_competing_evidence_subjects_publish_without_claiming_the_metric_is_missing():
    envelope = _envelope()
    task = _task([_trae(), _jokic()],
                 [_requirement("leaders_a", ["PLAYER_NAME"]),
                  _requirement("leaders_b", ["PLAYER_NAME"])],
                 ["PLAYER_NAME"])
    execution = _execution(envelope, _node(["leaders_a", "leaders_b"]))
    bindings = [
        binding.model_copy(update={"evidence_id": envelope.evidence_id})
        for binding in (
            _binding("PLAYER_NAME", "Trae Young", "leaders_a",
                     0, "1629027", "Trae Young"),
            _binding("PLAYER_NAME", "Nikola Jokic", "leaders_b",
                     1, "1628369", "Nikola Jokic"),
        )
    ]

    assert _answer(task, execution, envelope, bindings).splitlines() == [
        "Trae Young led the NBA with 880 assists in 2024-25."]


def test_propagated_task_binding_passes_admission_authority():
    envelope = _envelope()
    task = _task([_trae()], [_requirement("player_assists_leader",
                                         ["PLAYER_NAME", "AST"])],
                 ["PLAYER_NAME", "AST"])
    bindings = _q1_bindings(envelope)
    claims, _, _ = _admitted(
        task, _execution(envelope, _node(["player_assists_leader"])),
        envelope, bindings)
    propagated = [binding for binding in claims[0].output_bindings
                  if binding.requirement_kind == "task"]
    assert {binding.output_id for binding in propagated} == {"PLAYER_NAME", "AST"}
    execution = _execution(envelope, _node(["player_assists_leader"]))
    claim = _claim(list(claims[0].output_bindings), envelope.evidence_id)
    draft = DraftReport(sections=["Assists leader"], claims=[claim])
    verified = VerifiedClaim(
        claim_index=0,
        claim=claim,
        evidence_ids=[envelope.evidence_id],
        sources=[
            ClaimSource(
                evidence_id=envelope.evidence_id,
                source=envelope.source,
                capability=envelope.capability,
                observed_at=envelope.observed_at,
            )
        ],
        output_bindings=list(claims[0].output_bindings),
    )
    readmitted = admit_verified_claim_bindings(task, execution, draft, verified)
    assert len(readmitted.output_bindings) == 4


def test_preexisting_task_binding_is_not_duplicated():
    envelope = _envelope()
    task = _task([_trae()], [_requirement("player_assists_leader",
                                         ["PLAYER_NAME", "AST"])],
                 ["PLAYER_NAME", "AST"])
    evidence_binding = _q1_bindings(envelope)[0]
    task_binding = evidence_binding.model_copy(update={
        "requirement_kind": "task", "requirement_id": None})
    bindings = [evidence_binding, task_binding,
                _q1_bindings(envelope)[1]]
    _, _, by_key = _admitted(
        task, _execution(envelope, _node(["player_assists_leader"])),
        envelope, bindings)
    assert by_key[("task", None, "PLAYER_NAME")].status == "complete"
    assert by_key[("task", None, "PLAYER_NAME")].binding.requirement_id is None
    assert by_key[("task", None, "AST")].status == "complete"


_RATINGS_NODE = "ratings"
_RATINGS_REQUIREMENT = "ratings_2024_25"
_RATINGS_ALTERNATE = "ratings_alternate"
_RATINGS_UNIT = "points_per_100_possessions"
_RATINGS_TEAM_ID = "9001"
_RATINGS_VALUES = {"NET_RATING": 9.4, "OFF_RATING": 118.2, "DEF_RATING": 108.8}


def _ratings_team():
    return EntityRef(id=_RATINGS_TEAM_ID, type="team",
                     display_name="Sample Athletic")


def _ratings_envelope():
    return build_envelope(
        CAPABILITIES["team_ratings"],
        {"season": "2024-25", "team": _RATINGS_TEAM_ID},
        {"ok": True,
         "rows": [{"TEAM_ID": _RATINGS_TEAM_ID,
                   "TEAM_NAME": "Sample Athletic",
                   **_RATINGS_VALUES}],
         "meta": dict(_warehouse_meta())},
        entities=[_ratings_team()],
        observed_at=datetime.now(UTC),
    )


def _ratings_requirement(requirement_id, outputs):
    return EvidenceRequirement(
        id=requirement_id,
        description="sample team ratings 2024-25",
        capability_options=["team_ratings"],
        capability_arguments={"team": _RATINGS_TEAM_ID},
        requested_outputs=list(outputs),
    )


def _ratings_task(requirements=None):
    return TaskSpec(
        goal="sample team ratings 2024-25",
        mode="quick",
        deliverable="ratings",
        requested_outputs=list(_RATINGS_VALUES),
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[_ratings_team()],
        requirements=list(requirements or [
            _ratings_requirement(_RATINGS_REQUIREMENT, _RATINGS_VALUES)]),
    )


def _ratings_node(covers):
    return PlanNode(
        id=_RATINGS_NODE,
        description="sample team ratings 2024-25",
        capability_hints=["team_ratings"],
        covers_requirement_ids=list(covers),
        arguments={"season": "2024-25", "team": _RATINGS_TEAM_ID},
        status="complete",
    )


def _ratings_task_bindings(envelope, output_ids=_RATINGS_VALUES):
    return [
        EvidenceOutputBinding(
            requirement_kind="task",
            requirement_id=None,
            output_id=name,
            node_id=_RATINGS_NODE,
            evidence_id=envelope.evidence_id,
            selector=f"rows[0].{name}",
            row_selector="rows[0]",
            value={"kind": "float", "value": _RATINGS_VALUES[name]},
            subject_entity_type="team",
            subject_entity_id=_RATINGS_TEAM_ID,
            subject_selector="rows[0].TEAM_ID",
            unit={"kind": "declared", "value": _RATINGS_UNIT},
            domain="team_ratings",
        )
        for name in output_ids
    ]


def _ratings_run(task, node_covers, bindings=None, output_ids=_RATINGS_VALUES):
    envelope = _ratings_envelope()
    execution = _execution(envelope, _ratings_node(node_covers))
    claim = Claim(
        text="Sample Athletic rated 9.4 net in 2024-25.",
        kind="observed",
        evidence_ids=[envelope.evidence_id],
        output_bindings=list(
            _ratings_task_bindings(envelope, output_ids)
            if bindings is None else bindings),
    )
    draft = DraftReport(sections=["ratings"], claims=[claim])
    report = VerificationReport(
        status="pass",
        claim_results=[{"claim_index": 0, "supported": True, "reasons": []}])
    claims, gaps = _verified_claims(
        task, execution, draft, report, {envelope.evidence_id: envelope})
    statuses = build_output_statuses(task, claims, gaps)
    result = SimpleNamespace(
        task=task, execution=execution, draft=draft, verified_claims=claims,
        gaps=gaps, output_statuses=statuses, structural_flags=[],
        verification=SimpleNamespace(status=SimpleNamespace(value="pass")))
    return {
        (row["requirement_kind"], row["requirement_id"], row["output_id"]): row
        for row in (_public_output_status(result, item) for item in statuses)
    }


def _ratings_carry(node_covers=(_RATINGS_REQUIREMENT,), task=None):
    return _ratings_run(task or _ratings_task(), node_covers)


def test_task_level_bindings_also_satisfy_the_requirement_that_requests_them():
    carry = _ratings_carry()

    for name, value in _RATINGS_VALUES.items():
        requirement_row = carry[("evidence", _RATINGS_REQUIREMENT, name)]
        assert requirement_row["status"] == "complete"
        assert requirement_row["value"] == str(value)
        assert requirement_row["requirement_id"] == _RATINGS_REQUIREMENT


def test_requirement_rows_publish_the_same_authority_as_the_task_row():
    carry = _ratings_carry()

    for name in _RATINGS_VALUES:
        requirement_row = carry[("evidence", _RATINGS_REQUIREMENT, name)]
        task_row = carry[("task", None, name)]
        assert requirement_row["value"] == task_row["value"]
        assert requirement_row["unit"] == task_row["unit"] == _RATINGS_UNIT
        assert requirement_row["subject_id"] == task_row["subject_id"]
        assert requirement_row["subject_type"] == task_row["subject_type"] == "team"


def test_requirement_the_task_binding_cannot_authorize_stays_missing():
    carry = _ratings_carry(node_covers=())

    assert carry[("task", None, "NET_RATING")]["status"] == "complete"
    assert carry[("evidence", _RATINGS_REQUIREMENT,
                  "NET_RATING")]["status"] == "missing"


def test_requirement_requesting_only_one_output_leaves_the_others_task_owned():
    task = _ratings_task(requirements=[
        _ratings_requirement(_RATINGS_REQUIREMENT, ["NET_RATING"])])
    carry = _ratings_carry(task=task)

    assert carry[("evidence", _RATINGS_REQUIREMENT,
                  "NET_RATING")]["status"] == "complete"
    assert carry[("task", None, "OFF_RATING")]["status"] == "complete"
    assert ("evidence", _RATINGS_REQUIREMENT, "OFF_RATING") not in carry
    assert ("evidence", _RATINGS_REQUIREMENT, "DEF_RATING") not in carry


def test_every_requirement_requesting_the_output_is_satisfied_by_it():
    task = _ratings_task(requirements=[
        _ratings_requirement(_RATINGS_REQUIREMENT, ["NET_RATING"]),
        _ratings_requirement(_RATINGS_ALTERNATE, ["NET_RATING"]),
    ])
    envelope = _ratings_envelope()
    named = _ratings_task_bindings(envelope, ["NET_RATING"])[0].model_copy(
        update={"requirement_kind": "evidence",
                "requirement_id": _RATINGS_ALTERNATE})
    carry = _ratings_run(task, [_RATINGS_REQUIREMENT, _RATINGS_ALTERNATE],
                         [named], ["NET_RATING"])

    for requirement_id in (_RATINGS_ALTERNATE, _RATINGS_REQUIREMENT):
        assert carry[("evidence", requirement_id, "NET_RATING")]["status"] \
            == "complete"
    assert carry[("task", None, "NET_RATING")]["status"] == "complete"


class _StubModel:
    def __init__(self, payloads):
        self._payloads = list(payloads)


def _bos_task():
    return TaskSpec(
        goal="Celtics ratings 2024-25",
        mode="quick",
        deliverable="ratings",
        requested_outputs=["NET_RATING", "OFF_RATING", "DEF_RATING"],
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[EntityRef(id="1610612738", type="team",
                            display_name="Boston Celtics")],
        requirements=[EvidenceRequirement(
            id="celtics_ratings_2024_25",
            description="Celtics ratings 2024-25",
            capability_options=["team_ratings"],
            requested_outputs=["NET_RATING", "OFF_RATING", "DEF_RATING"],
        )],
    )


def test_planner_narrows_team_ratings_node_to_subject_team():
    from v2.adapters.models import ModelPlanner

    task = _bos_task()
    plan = Plan(nodes=[PlanNode(
        id="ratings",
        description="Celtics ratings 2024-25",
        capability_hints=["team_ratings"],
        covers_requirement_ids=["celtics_ratings_2024_25"],
        arguments={"season": "2024-25"},
    )])
    planner = ModelPlanner(_StubModel([]), provider="stub", model_name="stub",
                           capability_catalog={"team_ratings": {}})
    normalized = planner._normalize_plan(task, plan)
    assert normalized.nodes[0].arguments["team"] == "BOS"
    team_rows = [
        {"TEAM_ID": 1610612760, "TEAM_NAME": "Oklahoma City Thunder",
         "OFF_RATING": 118.1, "DEF_RATING": 105.4, "NET_RATING": 12.7},
        {"TEAM_ID": 1610612738, "TEAM_NAME": "Boston Celtics",
         "OFF_RATING": 118.2, "DEF_RATING": 108.8, "NET_RATING": 9.4},
    ]
    from shared.tools.league import get_ratings

    with patch("shared.tools.league._warehouse_or_live",
               return_value=(list(team_rows), {"method": "NBA box-score estimated possessions",
                                               "season": "2024-25"})):
        result = get_ratings.invoke({"season": "2024-25",
                                     "team": normalized.nodes[0].arguments["team"]})
    assert result["ok"] is True
    assert result["meta"]["method"] == "NBA box-score estimated possessions"
    assert len(result["rows"]) == 1
    assert result["rows"][0]["TEAM_ID"] == 1610612738
    assert result["rows"][0]["OFF_RATING"] == 118.2
    assert result["rows"][0]["DEF_RATING"] == 108.8
    assert result["rows"][0]["NET_RATING"] == 9.4
