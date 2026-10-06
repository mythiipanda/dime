from datetime import UTC, datetime
from unittest.mock import patch

from v2.adapters.capabilities import CAPABILITIES
from v2.adapters.core import build_envelope

def _bos_entry():
    from nba_api.stats.static import teams as _teams
    return next(t for t in _teams.get_teams() if t["abbreviation"] == "BOS")

def test_team_ratings_envelope_admits_team_identity_binding():
    entry = _bos_entry()
    team_id = entry["id"]
    team_name = entry["full_name"]
    team_abbrev = entry["abbreviation"]
    warehouse_rows = [
        {
            "TEAM_ID": team_id,
            "TEAM_NAME": team_name,
            "GP": 82,
            "W": 61,
            "L": 21,
            "OFF_RATING": 120.0,
            "DEF_RATING": 111.7,
            "NET_RATING": 8.3,
            "PACE": 99.0,
        }
    ]
    warehouse_meta = {
        "source": "warehouse",
        "season": "2024-25",
        "warehouse_id": "frozen-eval",
        "warehouse_sha256": "a" * 64,
    }
    from shared.tools.league import get_ratings

    with patch(
        "shared.tools.league._warehouse_or_live",
        return_value=(warehouse_rows, dict(warehouse_meta)),
    ):
        result = get_ratings.invoke({"season": "2024-25", "team": team_abbrev})
    assert result["ok"] is True
    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row.get("OFF_RATING") == 120.0
    assert row.get("DEF_RATING") == 111.7
    assert row.get("NET_RATING") == 8.3
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
        VerifiedClaim,
    )
    from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings

    subject = EntityRef(id=str(team_id), type="team", display_name=team_abbrev)
    envelope = build_envelope(
        CAPABILITIES["team_ratings"],
        {"season": "2024-25"},
        {"ok": True, "rows": result["rows"], "meta": dict(result["meta"])},
        entities=[subject],
        observed_at=datetime.now(UTC),
    )
    task = TaskSpec(
        goal="team ratings identity probe",
        mode="quick",
        deliverable="answer",
        season=SeasonRef(value="2024-25", source="user", confidence=1.0),
        entities=[subject],
        requirements=[
            EvidenceRequirement(
                id="ratings",
                description="team ratings identity probe",
                capability_options=["team_ratings"],
                requested_outputs=["NET_RATING"],
            )
        ],
    )
    node = PlanNode(
        id="ratings",
        description="team ratings identity probe",
        capability_hints=["team_ratings"],
        covers_requirement_ids=["ratings"],
        status="complete",
    )
    execution = ExecutionResult(
        plan=Plan(nodes=[node]),
        evidence_by_node={"ratings": envelope},
        attempts={"ratings": 1},
    )
    binding = EvidenceOutputBinding(
        requirement_kind="evidence",
        requirement_id="ratings",
        output_id="NET_RATING",
        node_id="ratings",
        evidence_id=envelope.evidence_id,
        selector="rows[0].NET_RATING",
        row_selector="rows[0]",
        value={"kind": "float", "value": 8.3},
        subject_entity_type="team",
        subject_entity_id=str(team_id),
        subject_selector="rows[0].TEAM_ID",
        unit={"kind": "declared", "value": "points_per_100_possessions"},
        domain="team_ratings",
    )
    claim = Claim(
        text="team net rating is 8.3",
        kind="observed",
        evidence_ids=[envelope.evidence_id],
        output_bindings=[binding],
    )
    draft = DraftReport(sections=["ratings"], claims=[claim])
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
        output_bindings=[binding],
    )
    admitted = admit_verified_claim_bindings(task, execution, draft, verified)
    assert admitted is verified
    assert admitted.output_bindings[0].value.value == 8.3
    assert envelope.rows[0].get("TEAM_ID") == team_id
