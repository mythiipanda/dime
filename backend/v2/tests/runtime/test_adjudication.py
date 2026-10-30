from v2.contracts import (
    Claim, ClaimResult, DraftReport, VerificationReport,
)
from v2.runtime.models import ExecutionResult
from v2.contracts import Plan, PlanNode, TaskSpec


def test_mixed_branch_matrix_preserves_complete_and_missing():
    from v2.contracts import EvidenceOutputBinding, EvidenceRequirement, VerifiedClaim
    from v2.runtime.models import build_output_statuses
    binding = EvidenceOutputBinding(requirement_id="record",output_id="WINS",
        node_id="facts",evidence_id="ev",selector="rows.WINS",
        value={"kind":"integer","value":61},unit={"kind":"declared","value":"count"},
        domain="standings")
    claim=Claim(text="61",kind="observed",evidence_ids=["ev"],output_bindings=[binding])
    task=TaskSpec(goal="record",mode="quick",deliverable="answer",requirements=[
        EvidenceRequirement(id="record",description="record",capability_options=["standings"],requested_outputs=["WINS"]),
        EvidenceRequirement(id="pace",description="pace",capability_options=["team_ratings"],requested_outputs=["PACE"])])
    matrix=build_output_statuses(task,[VerifiedClaim(claim_index=0,claim=claim,evidence_ids=["ev"],output_bindings=[binding])],[])
    assert [(x.requirement_id,x.status) for x in matrix]==[("record","complete"),("pace","missing")]

def test_status_identity_must_match_binding_and_roundtrips():
    import json, pytest
    from v2.contracts import OutputFinalStatus, EvidenceOutputBinding
    binding=EvidenceOutputBinding(requirement_kind="task",output_id="WINS",
        node_id="n",evidence_id="e",selector="rows.WINS",
        value={"kind":"integer","value":61},unit={"kind":"declared","value":"count"},
        domain="standings")
    status=OutputFinalStatus(requirement_kind="task",output_id="WINS",status="complete",
                             claim_index=0,binding=binding)
    assert OutputFinalStatus.model_validate_json(status.model_dump_json())==status
    payload=status.model_dump(mode="json");payload["output_id"]="LOSSES"
    with pytest.raises(Exception):OutputFinalStatus.model_validate_json(json.dumps(payload))
