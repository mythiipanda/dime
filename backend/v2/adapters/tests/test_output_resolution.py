from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))

WAREHOUSE = BACKEND / "data" / "warehouse.duckdb"

pytestmark = pytest.mark.skipif(
    not WAREHOUSE.exists(),
    reason=f"the warehouse is absent at {WAREHOUSE}")

SEASON = "2024-25"
NODE_ID = "leaders"
REQUIREMENT_ID = "counting_leader"


@pytest.fixture
def real_warehouse(monkeypatch):
    from shared import store
    from shared.tools import _core
    from v2.adapters import coverage

    connect = store.connect
    monkeypatch.setattr(store, "DB_PATH", WAREHOUSE)
    monkeypatch.setattr(store, "CANONICAL_DB_PATH", WAREHOUSE)
    monkeypatch.setattr(
        store, "connect", lambda read_only=True: connect(read_only=True))
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    store.warehouse_identity_cache_clear()
    _core.last_completed_season_cache_clear()
    coverage.coverage_cache_clear()
    yield WAREHOUSE
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    store.warehouse_identity_cache_clear()
    _core.last_completed_season_cache_clear()
    coverage.coverage_cache_clear()


def _spec():
    from v2.adapters.capabilities import CAPABILITIES

    return CAPABILITIES["qualified_leaders"]


def _envelope(metric):
    from v2.adapters.core import call_capability

    return call_capability(
        "qualified_leaders", {"stat_category": metric, "season": SEASON})


def _value(raw):
    if isinstance(raw, bool):
        return {"kind": "boolean", "value": raw}
    if isinstance(raw, int):
        return {"kind": "integer", "value": raw}
    if isinstance(raw, float):
        return {"kind": "float", "value": raw}
    return {"kind": "string", "value": str(raw)}


def _binding(output_id, leaf, raw, unit, envelope, row=0):
    from v2.contracts import EvidenceOutputBinding

    top = envelope.rows[row]
    subject_id = str(top.get("PLAYER_ID") or top.get("player_id"))
    return EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id=REQUIREMENT_ID,
        output_id=output_id,
        node_id=NODE_ID,
        evidence_id=envelope.evidence_id,
        selector=f"rows[{row}].{leaf}",
        row_selector=f"rows[{row}]",
        value=_value(raw),
        subject_entity_type="player",
        subject_entity_id=subject_id,
        subject_selector=f"rows[{row}].PLAYER_ID",
        unit=({"kind": "declared", "value": unit} if unit
              else {"kind": "unitless"}),
        domain="qualified_leaders",
    )


def _task(outputs, envelope, arguments):
    from v2.contracts import (
        EntityRef,
        EvidenceRequirement,
        SeasonRef,
        TaskSpec,
    )

    top = envelope.rows[0]
    entity = EntityRef(
        id=str(top.get("PLAYER_ID") or top.get("player_id")),
        type="player",
        display_name=str(top.get("PLAYER_NAME") or top.get("PLAYER")))
    return TaskSpec(
        goal="who leads the league",
        mode="quick",
        deliverable="leader, games, total and per-game",
        requested_outputs=list(outputs),
        season=SeasonRef(value=SEASON, source="user", confidence=1.0),
        entities=[entity],
        requirements=[EvidenceRequirement(
            id=REQUIREMENT_ID,
            description="counting leaderboard",
            capability_options=["qualified_leaders"],
            capability_arguments=dict(arguments),
            requested_outputs=list(outputs))],
    )


def _execution(envelope, arguments):
    from v2.contracts import Plan, PlanNode
    from v2.runtime.models import ExecutionResult

    return ExecutionResult(
        plan=Plan(nodes=[PlanNode(
            id=NODE_ID, description="counting leaderboard",
            capability_hints=["qualified_leaders"],
            covers_requirement_ids=[REQUIREMENT_ID],
            arguments=dict(arguments),
            status="complete")]),
        evidence_by_node={NODE_ID: envelope},
        attempts={NODE_ID: 1},
    )


def _admit(envelope, bindings, outputs, arguments):
    from v2.contracts import Claim, DraftReport, VerifiedClaim, ClaimSource
    from v2.runtime.models import admit_verified_claim_bindings

    task = _task(outputs, envelope, arguments)
    execution = _execution(envelope, arguments)
    claim = Claim(
        text="leader line", kind="observed",
        evidence_ids=[envelope.evidence_id],
        output_bindings=list(bindings))
    draft = DraftReport(sections=["leader"], claims=[claim])
    verified = VerifiedClaim(
        claim_index=0, claim=claim,
        evidence_ids=[envelope.evidence_id],
        sources=[ClaimSource(
            evidence_id=envelope.evidence_id, source=envelope.source,
            capability=envelope.capability, observed_at=envelope.observed_at)],
        output_bindings=list(bindings))
    return admit_verified_claim_bindings(task, execution, draft, verified)


def _publish(envelope, bindings, outputs, arguments):
    from v2.api.routes import _answer_text
    from v2.contracts import (
        Claim,
        DraftReport,
        VerificationReport,
    )
    from v2.runtime.loop import _verified_claims
    from v2.runtime.models import build_output_statuses

    task = _task(outputs, envelope, arguments)
    execution = _execution(envelope, arguments)
    claim = Claim(
        text="leader line", kind="observed",
        evidence_ids=[envelope.evidence_id],
        output_bindings=list(bindings))
    draft = DraftReport(sections=["leader"], claims=[claim])
    verification = VerificationReport(
        status="pass",
        claim_results=[{"claim_index": 0, "supported": True, "reasons": []}])
    admitted, gaps = _verified_claims(
        task, execution, draft, verification,
        {envelope.evidence_id: envelope})
    statuses = build_output_statuses(task, admitted, gaps)
    answer = _answer_text(SimpleNamespace(
        output_statuses=statuses, gaps=gaps, execution=execution,
        verified_claims=admitted, draft=draft))
    by_key = {(row.requirement_kind, row.requirement_id, row.output_id): row
              for row in statuses}
    return admitted, gaps, by_key, answer


def test_total_assists_games_played_and_player_bind_for_leaders_row(
        real_warehouse):
    from v2.adapters.capabilities import COUNT, resolve_metric_column

    spec = _spec()
    assert resolve_metric_column(spec, "TOTAL_ASSISTS") == "AST"
    assert resolve_metric_column(spec, "GAMES_PLAYED") == "GP"
    assert resolve_metric_column(spec, "PLAYER_NAME") == "PLAYER"
    envelope = _envelope("AST")
    top = envelope.rows[0]
    assert top["AST"] is not None
    assert top["GP"] is not None
    assert top["PLAYER"] is not None
    arguments = {"stat_category": "AST", "season": SEASON}
    bindings = [
        _binding("TOTAL_ASSISTS", "AST", top["AST"], COUNT, envelope),
        _binding("GAMES_PLAYED", "GP", top["GP"], COUNT, envelope),
        _binding("PLAYER_NAME", "PLAYER", top["PLAYER"], None, envelope),
    ]
    outputs = ["TOTAL_ASSISTS", "GAMES_PLAYED", "PLAYER_NAME"]
    admitted, gaps, by_key, answer = _publish(
        envelope, bindings, outputs, arguments)
    assert [by_key[("evidence", REQUIREMENT_ID, output_id)].status
            for output_id in outputs] == ["complete"] * len(outputs)
    assert {binding.output_id for binding in admitted[0].output_bindings} == set(outputs)
    assert [gap for gap in gaps if gap.blocks] == []
    assert "Some requested outputs could not be published." not in answer


def test_points_board_binds_its_own_total_games_player_and_per_game(
        real_warehouse):
    from v2.adapters.capabilities import COUNT, PER_GAME, resolve_metric_column

    spec = _spec()
    assert resolve_metric_column(spec, "TOTAL_POINTS") == "PTS"
    assert resolve_metric_column(spec, "POINTS_PER_GAME") == "PTS_PER_GAME"
    envelope = _envelope("PTS")
    top = envelope.rows[0]
    assert top["PTS"] is not None
    assert top["PTS_PER_GAME"] is not None
    arguments = {"stat_category": "PTS", "season": SEASON}
    bindings = [
        _binding("TOTAL_POINTS", "PTS", top["PTS"], COUNT, envelope),
        _binding("GAMES_PLAYED", "GP", top["GP"], COUNT, envelope),
        _binding("PLAYER_NAME", "PLAYER", top["PLAYER"], None, envelope),
        _binding(
            "POINTS_PER_GAME", "PTS_PER_GAME", top["PTS_PER_GAME"],
            PER_GAME, envelope),
    ]
    outputs = ["TOTAL_POINTS", "GAMES_PLAYED", "PLAYER_NAME", "POINTS_PER_GAME"]
    admitted, gaps, by_key, answer = _publish(
        envelope, bindings, outputs, arguments)
    assert [by_key[("evidence", REQUIREMENT_ID, output_id)].status
            for output_id in outputs] == ["complete"] * len(outputs)
    assert "Some requested outputs could not be published." not in answer


def test_future_counting_metric_binds_under_its_total_name():
    from v2.adapters.capabilities import (
        Capability,
        COUNT,
        resolve_metric_column,
    )

    spec = Capability(
        name="future_leaders",
        tool_name="get_future_leaders",
        units={"WOMBAT": COUNT, "GP": COUNT},
        metric_definitions={},
    )
    assert resolve_metric_column(spec, "TOTAL_WOMBAT") == "WOMBAT"
    assert resolve_metric_column(spec, "WOMBAT") == "WOMBAT"
    assert resolve_metric_column(spec, "TOTAL_HOME_RUNS") is None


def test_per_game_companion_binds_under_both_names(real_warehouse):
    from v2.adapters.capabilities import PER_GAME, resolve_metric_column

    spec = _spec()
    assert resolve_metric_column(spec, "AST_PER_GAME") == "AST_PER_GAME"
    assert resolve_metric_column(spec, "ASSISTS_PER_GAME") == "AST_PER_GAME"
    envelope = _envelope("AST")
    top = envelope.rows[0]
    arguments = {"stat_category": "AST", "season": SEASON}
    direct = _binding(
        "AST_PER_GAME", "AST_PER_GAME", top["AST_PER_GAME"],
        PER_GAME, envelope)
    admitted = _admit(
        envelope, [direct], ["AST_PER_GAME"], arguments)
    assert admitted.output_bindings[0].value.value == top["AST_PER_GAME"]
    planner = _binding(
        "ASSISTS_PER_GAME", "AST_PER_GAME", top["AST_PER_GAME"],
        PER_GAME, envelope)
    admitted = _admit(
        envelope, [planner], ["ASSISTS_PER_GAME"], arguments)
    assert admitted.output_bindings[0].value.value == top["AST_PER_GAME"]


def test_row_belonging_to_a_different_player_is_rejected(real_warehouse):
    from v2.adapters.capabilities import COUNT

    envelope = _envelope("AST")
    assert len(envelope.rows) >= 2
    top = envelope.rows[0]
    other = envelope.rows[1]
    assert str(top.get("PLAYER_ID")) != str(other.get("PLAYER_ID"))
    from v2.contracts import EvidenceOutputBinding

    binding = EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id=REQUIREMENT_ID,
        output_id="TOTAL_ASSISTS",
        node_id=NODE_ID,
        evidence_id=envelope.evidence_id,
        selector="rows[1].AST",
        row_selector="rows[1]",
        value=_value(other["AST"]),
        subject_entity_type="player",
        subject_entity_id=str(top.get("PLAYER_ID")),
        subject_selector="rows[1].PLAYER_ID",
        unit={"kind": "declared", "value": COUNT},
        domain="qualified_leaders",
    )
    with pytest.raises(ValueError, match="row does not match subject"):
        _admit(envelope, [binding], ["TOTAL_ASSISTS"],
               {"stat_category": "AST", "season": SEASON})


def test_name_matching_no_rule_and_no_declared_output_resolves_to_nothing():
    spec = _spec()
    assert spec.units.get("HOME_RUNS") is None
    from v2.adapters.capabilities import resolve_metric_column

    assert resolve_metric_column(spec, "HOME_RUNS") is None
    assert resolve_metric_column(spec, "TOTAL_HOME_RUNS") is None
