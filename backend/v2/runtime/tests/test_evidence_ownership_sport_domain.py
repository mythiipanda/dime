from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))

WAREHOUSE = BACKEND / "data" / "warehouse.duckdb"

pytestmark = pytest.mark.skipif(
    not WAREHOUSE.exists(), reason=f"the warehouse is absent at {WAREHOUSE}")

SEASON = "2024-25"
NODE_ID = "assist_leader"
REQUIREMENT_ID = "assist_leader"


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


def _envelope():
    from v2.adapters.core import call_capability

    return call_capability(
        "qualified_leaders", {"stat_category": "AST", "season": SEASON})


def _value(raw):
    if isinstance(raw, bool):
        return {"kind": "boolean", "value": raw}
    if isinstance(raw, int):
        return {"kind": "integer", "value": raw}
    if isinstance(raw, float):
        return {"kind": "float", "value": raw}
    return {"kind": "string", "value": str(raw)}


def _bindings(envelope, domain):
    from v2.adapters.capabilities import COUNT, PER_GAME

    top = envelope.rows[0]
    subject = str(top.get("PLAYER_ID") or top.get("player_id"))
    specs = [
        ("PLAYER_NAME", "PLAYER", None),
        ("TOTAL_ASSISTS", "AST", COUNT),
        ("GAMES_PLAYED", "GP", COUNT),
        ("ASSISTS_PER_GAME", "AST_PER_GAME", PER_GAME),
    ]
    from v2.contracts import EvidenceOutputBinding

    out = []
    for output_id, leaf, unit in specs:
        out.append(EvidenceOutputBinding(
            requirement_kind="evidence",
            requirement_id=REQUIREMENT_ID,
            output_id=output_id,
            node_id=NODE_ID,
            evidence_id=envelope.evidence_id,
            selector=f"rows[0].{leaf}",
            row_selector="rows[0]",
            value=_value(top[leaf]),
            subject_entity_type="player",
            subject_entity_id=subject,
            subject_selector="rows[0].PLAYER_ID",
            unit=({"kind": "declared", "value": unit} if unit else {"kind": "unitless"}),
            domain=domain,
        ))
    return out


def _task(envelope, outputs):
    from v2.contracts import EntityRef, EvidenceRequirement, SeasonRef, TaskSpec

    top = envelope.rows[0]
    entity = EntityRef(
        id=str(top.get("PLAYER_ID") or top.get("player_id")),
        type="player",
        display_name=str(top.get("PLAYER_NAME") or top.get("PLAYER")))
    return TaskSpec(
        goal="who led the league in assists",
        mode="quick",
        deliverable="leader with totals",
        requested_outputs=list(outputs),
        season=SeasonRef(value=SEASON, source="user", confidence=1.0),
        entities=[entity],
        requirements=[EvidenceRequirement(
            id=REQUIREMENT_ID,
            description="assists leaderboard",
            capability_options=["qualified_leaders"],
            capability_arguments={"stat_category": "AST", "season": SEASON},
            requested_outputs=list(outputs))],
    )


def _execution(envelope):
    from v2.contracts import Plan, PlanNode
    from v2.runtime.models import ExecutionResult

    return ExecutionResult(
        plan=Plan(nodes=[PlanNode(
            id=NODE_ID, description="assists leaderboard",
            capability_hints=["qualified_leaders"],
            covers_requirement_ids=[REQUIREMENT_ID],
            arguments={"stat_category": "AST", "season": SEASON},
            status="complete")]),
        evidence_by_node={NODE_ID: envelope},
        attempts={NODE_ID: 1},
    )


def _admit(envelope, bindings, outputs):
    from v2.contracts import Claim, ClaimSource, DraftReport, VerifiedClaim
    from v2.runtime.models import admit_verified_claim_bindings

    task = _task(envelope, outputs)
    execution = _execution(envelope)
    claim = Claim(
        text="assists leader line", kind="observed",
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


def _publish(envelope, bindings, outputs):
    from v2.runtime.models import build_output_statuses

    admitted = _admit(envelope, bindings, outputs)
    statuses = build_output_statuses(
        _task(envelope, outputs), [admitted], [])
    by_key = {(row.requirement_kind, row.requirement_id, row.output_id): row
              for row in statuses}
    return admitted, by_key


def test_assists_question_publishes_all_four_outputs_with_citations(real_warehouse):
    envelope = _envelope()
    top = envelope.rows[0]
    assert top["AST"] is not None
    assert top["GP"] is not None
    assert top["AST_PER_GAME"] is not None
    assert top["PLAYER"] is not None
    outputs = ["PLAYER_NAME", "TOTAL_ASSISTS", "GAMES_PLAYED", "ASSISTS_PER_GAME"]
    bindings = _bindings(envelope, "basketball")
    admitted, by_key = _publish(envelope, bindings, outputs)
    assert [by_key[("evidence", REQUIREMENT_ID, output_id)].status
            for output_id in outputs] == ["complete"] * len(outputs)
    assert admitted.evidence_ids == [envelope.evidence_id]
    assert {item.output_id for item in admitted.output_bindings} == set(outputs)


def test_binding_naming_sport_publishes(real_warehouse):
    envelope = _envelope()
    outputs = ["TOTAL_ASSISTS"]
    admitted = _admit(envelope, _bindings(envelope, "basketball")[:2][1:], outputs)
    assert admitted.output_bindings[0].value.value == envelope.rows[0]["AST"]


def test_binding_naming_capability_name_still_publishes(real_warehouse):
    envelope = _envelope()
    outputs = ["TOTAL_ASSISTS"]
    bindings = _bindings(envelope, "qualified_leaders")
    selected = [item for item in bindings if item.output_id == "TOTAL_ASSISTS"]
    admitted = _admit(envelope, selected, outputs)
    assert admitted.output_bindings[0].value.value == envelope.rows[0]["AST"]


def test_binding_naming_foreign_domain_is_rejected(real_warehouse):
    envelope = _envelope()
    outputs = ["TOTAL_ASSISTS"]
    bindings = _bindings(envelope, "football")
    selected = [item for item in bindings if item.output_id == "TOTAL_ASSISTS"]
    with pytest.raises(ValueError, match="binding domain does not match capability"):
        _admit(envelope, selected, outputs)


def test_wrong_subject_negative_is_still_rejected(real_warehouse):
    from v2.contracts import EvidenceOutputBinding

    envelope = _envelope()
    assert len(envelope.rows) >= 2
    top = envelope.rows[0]
    other = envelope.rows[1]
    assert str(top.get("PLAYER_ID")) != str(other.get("PLAYER_ID"))
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
        unit={"kind": "declared", "value": "count"},
        domain="basketball",
    )
    with pytest.raises(ValueError, match="row does not match subject"):
        _admit(envelope, [binding], ["TOTAL_ASSISTS"])
