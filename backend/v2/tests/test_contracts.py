from datetime import datetime

import pytest
from pydantic import ValidationError

from v2.contracts import (
    Claim,
    ClaimKind,
    EvidenceEnvelope,
    Plan,
    PlanNode,
)


def test_plan_accepts_dag():
    plan = Plan(nodes=[
        PlanNode(id="baseline", description="Get baseline",
                 completion_test="baseline evidence exists"),
        PlanNode(id="report", description="Write report",
                 depends_on=["baseline"], completion_test="report exists"),
    ])
    assert plan.nodes[1].depends_on == ["baseline"]


def test_plan_rejects_cycle():
    with pytest.raises(ValidationError, match="acyclic"):
        Plan(nodes=[
            PlanNode(id="a", description="A", depends_on=["b"],
                     completion_test="done"),
            PlanNode(id="b", description="B", depends_on=["a"],
                     completion_test="done"),
        ])


def test_claim_support_rules():
    with pytest.raises(ValidationError, match="require evidence"):
        Claim(text="Boston won 60 games", kind=ClaimKind.OBSERVED)
    claim = Claim(text="Boston projects to 55 wins", kind=ClaimKind.PROJECTION,
                  confidence=0.6)
    assert claim.confidence == 0.6


def test_evidence_round_trip():
    evidence = EvidenceEnvelope(
        evidence_id="ratings:bos:2025-26",
        capability="team_ratings",
        source="warehouse:silver_team_ratings",
        observed_at=datetime(2026, 9, 14, 14, 0),
        season="2025-26",
        rows=[{"TEAM": "BOS", "NET_RATING": 8.2}],
        units={"NET_RATING": "points per 100 possessions"},
    )
    assert EvidenceEnvelope.model_validate_json(
        evidence.model_dump_json()).rows[0]["TEAM"] == "BOS"
