from datetime import UTC, datetime

import pytest

from v2.contracts import (
    Claim,
    ClaimSource,
    DraftReport,
    EntityRef,
    EvidenceEnvelope,
    EvidenceOutputBinding,
    EvidenceRequirement,
    Plan,
    PlanNode,
    TaskSpec,
    VerifiedClaim,
)
from v2.runtime.models import (
    ExecutionResult,
    _BindingAdmission,
    admit_verified_claim_bindings,
)

_TRUE_NODE = "okc_standings_2024_25"
_GHOST_NODE = "node_standings"
_EVIDENCE_ID = "standings:a34a5a591d13db55"
_GHOST_EVIDENCE_ID = "standings:0000000000000000"
_REQUIREMENT = "okc_record_2024_25"
_TEAM_ID = "1610612737"

def _envelope():
    return EvidenceEnvelope(
        evidence_id=_EVIDENCE_ID,
        capability="standings",
        source="test:warehouse",
        observed_at=datetime.now(UTC),
        season="2024-25",
        rows=[{"TEAM_ID": _TEAM_ID, "WINS": 68, "LOSSES": 14}],
        units={"WINS": "count", "LOSSES": "count"},
        entities=[EntityRef(id=_TEAM_ID, type="team", display_name="Test Club")],
    )

def _task():
    return TaskSpec(
        goal="win-loss record in 2024-25",
        mode="quick",
        deliverable="answer",
        requested_outputs=["WINS", "LOSSES"],
        entities=[EntityRef(id=_TEAM_ID, type="team", display_name="Test Club")],
        requirements=[
            EvidenceRequirement(
                id=_REQUIREMENT,
                description="2024-25 win-loss record",
                capability_options=["standings"],
                requested_outputs=["WINS", "LOSSES"],
            )
        ],
    )

def _bindings(node_id, evidence_id):
    return [
        EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id=_REQUIREMENT,
            output_id="WINS",
            node_id=node_id,
            evidence_id=evidence_id,
            selector="rows[0].WINS",
            row_selector="rows[0]",
            value={"kind": "integer", "value": 68},
            subject_entity_type="team",
            subject_entity_id=_TEAM_ID,
            subject_selector="rows[0].TEAM_ID",
            unit={"kind": "declared", "value": "count"},
            domain="standings",
        ),
        EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id=_REQUIREMENT,
            output_id="LOSSES",
            node_id=node_id,
            evidence_id=evidence_id,
            selector="rows[0].LOSSES",
            row_selector="rows[0]",
            value={"kind": "integer", "value": 14},
            subject_entity_type="team",
            subject_entity_id=_TEAM_ID,
            subject_selector="rows[0].TEAM_ID",
            unit={"kind": "declared", "value": "count"},
            domain="standings",
        ),
    ]

def _node():
    return PlanNode(
        id=_TRUE_NODE,
        description="standings for the 2024-25 season",
        capability_hints=["standings"],
        covers_requirement_ids=[_REQUIREMENT],
        status="complete",
    )

def _admit(bindings):
    envelope = _envelope()
    execution = ExecutionResult(
        plan=Plan(nodes=[_node()]),
        evidence_by_node={_TRUE_NODE: envelope},
        attempts={_TRUE_NODE: 1},
    )
    evidence_ids = list(dict.fromkeys(item.evidence_id for item in bindings))
    claim = Claim(
        text="verified claim",
        kind="observed",
        evidence_ids=evidence_ids,
        output_bindings=bindings,
    )
    draft = DraftReport(sections=["claim"], claims=[claim])
    verified = VerifiedClaim(
        claim_index=0,
        claim=claim,
        evidence_ids=evidence_ids,
        sources=[
            ClaimSource(
                evidence_id=evidence_id,
                source=envelope.source,
                capability=envelope.capability,
                observed_at=envelope.observed_at,
            )
            for evidence_id in evidence_ids
        ],
        output_bindings=bindings,
    )
    return admit_verified_claim_bindings(_task(), execution, draft, verified)

def test_nonexistent_node_with_real_evidence_binds():
    admitted = _admit(_bindings(_GHOST_NODE, _EVIDENCE_ID))
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["WINS"].value.value == 68
    assert by_output["LOSSES"].value.value == 14

def test_invented_evidence_with_true_node_admits_with_corrected_id():
    admitted = _admit(_bindings(_TRUE_NODE, _GHOST_EVIDENCE_ID))
    assert [item.evidence_id for item in admitted.output_bindings] == [_EVIDENCE_ID, _EVIDENCE_ID]
    assert admitted.evidence_ids == [_EVIDENCE_ID]
    assert [item.evidence_id for item in admitted.sources] == [_EVIDENCE_ID]
    by_output = {item.output_id: item for item in admitted.output_bindings}
    assert by_output["WINS"].value.value == 68
    assert by_output["LOSSES"].value.value == 14

def test_invented_evidence_with_true_node_wrong_values_rejects():
    bindings = _bindings(_TRUE_NODE, _GHOST_EVIDENCE_ID)
    bad = [
        item.model_copy(update={"value": item.value.model_copy(update={"value": 999})})
        for item in bindings
    ]
    with pytest.raises(ValueError, match="binding value"):
        _admit(bad)


_SQL_NODE = "sga_per_game_2024_25"
_SQL_REQUIREMENT = "per_game_from_player_season"
_SQL_EVIDENCE_ID = "sql_exec:r507"
_SQL_EXPECTED = (
    "SELECT PLAYER, TEAM, GP, PPG, RPG, APG, TS_PCT FROM silver_player_season "
    "WHERE PLAYER = 'Shai Gilgeous-Alexander' AND _season = '2024-25'"
)
_SQL_ALIASED = (
    "SELECT PLAYER, TEAM, GP, PPG, RPG, APG, TS_PCT, PPG AS \"PTS\", "
    "RPG AS \"REB\", APG AS \"AST\" FROM silver_player_season "
    "WHERE PLAYER = 'Shai Gilgeous-Alexander' AND _season = '2024-25'"
)


def _sql_requirement_arguments(*, season=None, expected_sql=_SQL_EXPECTED):
    arguments = {"sql": expected_sql}
    if season is not None:
        arguments["season"] = season
    return arguments


def _check_sql_scope(node_arguments, *, season=None, expected_sql=_SQL_EXPECTED):
    task = TaskSpec(
        goal="SGA per game",
        mode="quick",
        deliverable="answer",
        requested_outputs=["PTS"],
        requirements=[
            EvidenceRequirement(
                id=_SQL_REQUIREMENT,
                description="per game",
                capability_options=["sql_exec"],
                capability_arguments=_sql_requirement_arguments(
                    season=season, expected_sql=expected_sql),
                requested_outputs=["PTS"],
            )
        ],
    )
    evidence = EvidenceEnvelope(
        evidence_id=_SQL_EVIDENCE_ID,
        capability="sql_exec",
        source="test:warehouse",
        observed_at=datetime.now(UTC),
        season="2024-25",
        rows=[{"PTS": 32.7}],
    )
    node = PlanNode(
        id=_SQL_NODE,
        description="per game",
        capability_hints=["sql_exec"],
        covers_requirement_ids=[_SQL_REQUIREMENT],
        arguments=node_arguments,
        status="complete",
    )
    execution = ExecutionResult(
        plan=Plan(nodes=[node]),
        evidence_by_node={_SQL_NODE: evidence},
        attempts={_SQL_NODE: 1},
    )
    claim = Claim(
        text="32.7 points",
        kind="observed",
        evidence_ids=[_SQL_EVIDENCE_ID],
    )
    draft = DraftReport(sections=["answer"], claims=[claim])
    verified = VerifiedClaim(
        claim_index=0,
        claim=claim,
        evidence_ids=[_SQL_EVIDENCE_ID],
        sources=[ClaimSource(
            evidence_id=_SQL_EVIDENCE_ID,
            source=evidence.source,
            capability=evidence.capability,
            observed_at=evidence.observed_at,
        )],
    )
    admission = _BindingAdmission(task, execution, draft, verified)
    binding = EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id=_SQL_REQUIREMENT,
        output_id="PTS",
        node_id=_SQL_NODE,
        evidence_id=_SQL_EVIDENCE_ID,
        selector="rows[0].PTS",
        value={"kind": "float", "value": 32.7},
        unit={"kind": "declared", "value": "points_per_game"},
        domain="sql_exec",
    )
    admission._check_requirement_scope(
        binding, node, evidence,
        admission.evidence_requirements[_SQL_REQUIREMENT])


def test_requirement_scope_accepts_direct_column_alias_superset():
    _check_sql_scope({"sql": _SQL_ALIASED})


@pytest.mark.parametrize("sql", [
    _SQL_ALIASED.replace("Shai Gilgeous-Alexander", "Jayson Tatum"),
    _SQL_ALIASED.replace("2024-25", "2023-24"),
    _SQL_ALIASED + " AND PPG > 10",
    _SQL_ALIASED.replace("silver_player_season", "silver_other_season"),
    "SELECT PLAYER, TEAM, GP, PPG, APG, TS_PCT, PPG AS \"PTS\", APG AS \"AST\" "
    "FROM silver_player_season WHERE PLAYER = 'Shai Gilgeous-Alexander' "
    "AND _season = '2024-25'",
    _SQL_ALIASED.replace("PPG AS \"PTS\"", "SUM(PPG) AS \"PTS\""),
    _SQL_ALIASED.replace("PPG AS \"PTS\"", "ROUND(PPG, 1) AS \"PTS\""),
    _SQL_ALIASED + " AND PPG > (SELECT 1)",
    "WITH src AS (" + _SQL_EXPECTED + ") SELECT PLAYER, TEAM, GP, PPG, RPG, "
    "APG, TS_PCT, PPG AS \"PTS\" FROM src",
    _SQL_ALIASED.replace(
        "FROM silver_player_season",
        "FROM silver_player_season JOIN silver_hist_player_seasons "
        "ON silver_player_season.PLAYER = silver_hist_player_seasons.player_name"),
    _SQL_ALIASED + " GROUP BY PLAYER",
    _SQL_ALIASED + " ORDER BY PPG",
    _SQL_ALIASED + " LIMIT 1",
    _SQL_ALIASED.replace("SELECT ", "SELECT DISTINCT ", 1),
    "SELECT *, PPG AS \"PTS\" FROM silver_player_season WHERE PLAYER = "
    "'Shai Gilgeous-Alexander' AND _season = '2024-25'",
])
def test_requirement_scope_keeps_rejecting_scope_and_expression_drift(sql):
    with pytest.raises(ValueError, match="binding node scope"):
        _check_sql_scope({"sql": sql})


def test_requirement_scope_keeps_non_sql_arguments_strict():
    _check_sql_scope({"sql": _SQL_ALIASED, "season": "2024-25"}, season="2024-25")
    with pytest.raises(ValueError, match="binding node scope"):
        _check_sql_scope(
            {"sql": _SQL_ALIASED, "season": "2024-25 "}, season="2024-25")
    with pytest.raises(ValueError, match="binding node scope"):
        _check_sql_scope({"sql": _SQL_ALIASED}, season="2024-25")


_R512_LITERAL_EXPECTED = (
    "SELECT PLAYER, TEAM, PPG FROM silver_player_season "
    "WHERE PLAYER = 'PlayerA' AND TEAM = 'BOS' AND _season = '2024-25'"
)


@pytest.mark.parametrize("sql", [
    _R512_LITERAL_EXPECTED.replace("'PlayerA'", "'playera'"),
    _R512_LITERAL_EXPECTED.replace("'PlayerA'", "'PLAYERA'"),
    _R512_LITERAL_EXPECTED.replace("'BOS'", "'bos'"),
    _R512_LITERAL_EXPECTED.replace("'2024-25'", "'2024-25 '"),
])
def test_requirement_scope_rejects_literal_case_and_value_drift(sql):
    with pytest.raises(ValueError, match="binding node scope"):
        _check_sql_scope(
            {"sql": sql}, expected_sql=_R512_LITERAL_EXPECTED)


def test_requirement_scope_accepts_identifier_and_alias_case_changes():
    _check_sql_scope(
        {"sql": (
            "select player, team, ppg from SILVER_PLAYER_SEASON "
            "where PLAYER = 'PlayerA' and team = 'BOS' and _season = '2024-25'"
        )},
        expected_sql=_R512_LITERAL_EXPECTED,
    )
    _check_sql_scope(
        {"sql": (
            "select player, team, ppg, ppg as pts from SILVER_PLAYER_SEASON "
            "where PLAYER = 'PlayerA' and team = 'BOS' and _season = '2024-25'"
        )},
        expected_sql=_R512_LITERAL_EXPECTED,
    )


def test_requirement_scope_accepts_regular_season_literal_normalization():
    expected = (
        "SELECT COUNT(*) AS games, MAX(pts) AS best FROM silver_hist_gamelogs "
        "WHERE season_type = 'Regular Season' AND team_name = 'Boston Celtics'"
    )
    _check_sql_scope(
        {"sql": expected.replace("'Regular Season'", "'regular-season'")},
        expected_sql=expected,
    )
