from __future__ import annotations

from types import SimpleNamespace

import duckdb
import pytest

from v2.adapters.capabilities import CAPABILITIES, COUNT, PER_GAME
from v2.adapters.core import call_capability
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
from v2.runtime.models import (ExecutionResult, admit_verified_claim_bindings,
                               build_output_statuses,
                               withheld_claim_indices)

_SEASON = "2024-25"
_NODE_ID = "leaders"
_REQUIREMENT_ID = "counting_leader"
_COUNTING_METRICS = (
    "PTS", "REB", "AST", "STL", "BLK", "OREB", "DREB", "TOV", "PF",
    "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA",
)
_LEADER = ("Alpha Guard", "AAA", 900001, 76, 880)
_SECOND = ("Beta Guard", "BBB", 900002, 70, 500)
_NO_GAMES = ("Gamma Guard", "CCC", 900003, 0, 250)
_BOARD = (_LEADER, _SECOND, _NO_GAMES)


@pytest.fixture()
def leaders_warehouse(monkeypatch, tmp_path):
    from shared import store
    from shared.tools import league

    warehouse = tmp_path / "warehouse.duckdb"
    connection = duckdb.connect(str(warehouse))
    for metric in _COUNTING_METRICS:
        connection.execute(
            f"CREATE TABLE silver_leaders_{metric.lower()} ("
            "PLAYER_ID BIGINT, RANK BIGINT, PLAYER VARCHAR, TEAM VARCHAR, "
            f"GP BIGINT, MIN BIGINT, {metric} BIGINT, _source VARCHAR, "
            "_season VARCHAR, _fetched_at VARCHAR)")
        for rank, row in enumerate(_BOARD, 1):
            name, team, player_id, games, total = row
            connection.execute(
                f"INSERT INTO silver_leaders_{metric.lower()} VALUES "
                "(?, ?, ?, ?, ?, ?, ?, 'fixture', ?, ?)",
                [player_id, rank, name, team, games, games * 36, total,
                 _SEASON, "2025-06-30T00:00:00+00:00"])
    connection.close()
    monkeypatch.setattr(store, "DB_PATH", warehouse)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store._tables_cache.clear()
    store._pool_evict_all()
    store.warehouse_identity_cache_clear()
    league._clear_warehouse_schema_cache()
    yield warehouse
    league._clear_warehouse_schema_cache()

def _envelope(metric="AST"):
    return call_capability(
        "qualified_leaders", {"stat_category": metric, "season": _SEASON})

def _binding(output_id, leaf, value, unit, *, row=0, subject=_LEADER,
             subject_selector=None):
    return EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id=_REQUIREMENT_ID,
        output_id=output_id,
        node_id=_NODE_ID,
        evidence_id="evidence:leaders",
        selector=f"rows[{row}].{leaf}",
        row_selector=f"rows[{row}]",
        value=value,
        subject_entity_type="player",
        subject_entity_id=str(subject[2]),
        subject_selector=subject_selector or f"rows[{row}].PLAYER_ID",
        unit={"kind": "declared", "value": unit},
        domain="qualified_leaders",
    )


def _per_game_binding(output_id, leaf, rate, unit=PER_GAME, **kwargs):
    return _binding(output_id, leaf, {"kind": "float", "value": rate},
                    unit, **kwargs)

def _task(outputs, entity=_LEADER):
    return TaskSpec(
        goal="who leads the league, and at what rate",
        mode="quick",
        deliverable="leader, games, total and per-game",
        requested_outputs=list(outputs),
        season=SeasonRef(value=_SEASON, source="user", confidence=1.0),
        entities=[EntityRef(id=str(entity[2]), type="player",
                            display_name=entity[0])],
        requirements=[EvidenceRequirement(
            id=_REQUIREMENT_ID,
            description="counting leaderboard with per-game context",
            capability_options=["qualified_leaders"],
            capability_arguments={"stat_category": "AST", "season": _SEASON},
            requested_outputs=list(outputs))],
    )

def _execution(envelope):
    return ExecutionResult(
        plan=Plan(nodes=[PlanNode(
            id=_NODE_ID, description="counting leaderboard",
            capability_hints=["qualified_leaders"],
            covers_requirement_ids=[_REQUIREMENT_ID],
            arguments={"stat_category": "AST", "season": _SEASON},
            status="complete")]),
        evidence_by_node={_NODE_ID: envelope},
        attempts={_NODE_ID: 1},
    )

def _verified(envelope, bindings, claim_text="leader line"):
    stamped = [binding.model_copy(update={"evidence_id": envelope.evidence_id})
               for binding in bindings]
    claim = Claim(
        text=claim_text, kind="observed",
        evidence_ids=[envelope.evidence_id],
        output_bindings=stamped)
    draft = DraftReport(sections=["leader"], claims=[claim])
    verified = VerifiedClaim(
        claim_index=0, claim=claim,
        evidence_ids=[envelope.evidence_id],
        sources=[ClaimSource(
            evidence_id=envelope.evidence_id, source=envelope.source,
            capability=envelope.capability, observed_at=envelope.observed_at)],
        output_bindings=stamped)
    return draft, verified

def _admit(envelope, bindings, outputs, entity=_LEADER):
    task = _task(outputs, entity)
    execution = _execution(envelope)
    draft, verified = _verified(envelope, bindings)
    return admit_verified_claim_bindings(task, execution, draft, verified)


@pytest.mark.parametrize("metric", _COUNTING_METRICS)
def test_counting_leader_row_carries_its_own_per_game_companion(
        leaders_warehouse, metric):
    envelope = _envelope(metric)
    assert envelope.rows[0][metric] == _LEADER[4]
    assert envelope.rows[0][f"{metric}_PER_GAME"] == pytest.approx(
        round(_LEADER[4] / _LEADER[3], 1))
    assert envelope.rows[1][f"{metric}_PER_GAME"] == pytest.approx(
        round(_SECOND[4] / _SECOND[3], 1))

def test_envelope_units_carry_every_ranked_counting_companion(
        leaders_warehouse):
    assert _envelope().units["GP"] == COUNT
    for metric in _COUNTING_METRICS:
        assert _envelope(metric).units[f"{metric}_PER_GAME"] == PER_GAME

def test_every_counting_leader_metric_declares_a_per_game_companion():
    units = CAPABILITIES["qualified_leaders"].units
    counted = {key for key, unit in units.items()
               if unit == COUNT and key != "GP"}
    companions = {key for key, unit in units.items() if unit == PER_GAME}
    assert companions
    assert {key.removesuffix("_PER_GAME") for key in companions} == counted

@pytest.mark.parametrize("unit", ["per_game", "per game"])
def test_per_game_companion_unit_admits_the_binding(leaders_warehouse, unit):
    envelope = _envelope()
    binding = _per_game_binding(
        "ASSIST_PER_GAME", "AST_PER_GAME", 11.6, unit=unit)
    admitted = _admit(envelope, [binding], ["ASSIST_PER_GAME"])
    assert admitted.output_bindings[0].value.value == pytest.approx(11.6)

def test_per_game_companion_of_another_stat_is_rejected(leaders_warehouse):
    envelope = _envelope()
    binding = _per_game_binding("ASSIST_PER_GAME", "REB_PER_GAME", 3.1)
    with pytest.raises(ValueError, match="selector metric does not match"):
        _admit(envelope, [binding], ["ASSIST_PER_GAME"])


def test_per_game_companion_read_off_another_row_is_rejected(leaders_warehouse):
    envelope = _envelope()
    binding = _per_game_binding(
        "ASSIST_PER_GAME", "AST_PER_GAME", 7.1, row=1, subject=_LEADER,
        subject_selector="rows[1].PLAYER_ID")
    with pytest.raises(ValueError, match="row does not match subject"):
        _admit(envelope, [binding], ["ASSIST_PER_GAME"])

def test_zero_game_row_yields_no_per_game_companion(leaders_warehouse):
    envelope = _envelope()
    row = envelope.rows[2]
    assert row["GP"] == 0
    assert "AST_PER_GAME" not in row
    binding = _per_game_binding(
        "ASSIST_PER_GAME", "AST_PER_GAME", 0.0, row=2, subject=_NO_GAMES)
    with pytest.raises(ValueError, match="exactly one value"):
        _admit(envelope, [binding], ["ASSIST_PER_GAME"], entity=_NO_GAMES)


@pytest.fixture()
def anyio_backend():
    return "asyncio"
