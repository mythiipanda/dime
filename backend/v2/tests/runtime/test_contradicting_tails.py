from __future__ import annotations

from types import SimpleNamespace

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

PROSE = "The New York Knicks won the 2024-25 season series 4-2."

def _binding(output_id: str) -> EvidenceOutputBinding:
    return EvidenceOutputBinding(
        requirement_kind="task",
        requirement_id=None,
        output_id=output_id,
        node_id="n1",
        evidence_id="ev",
        selector="rows.summary",
        value={"kind": "integer", "value": 4},
        unit={"kind": "unitless"},
        domain="season_series",
    )

def _result() -> SimpleNamespace:
    claim = Claim(
        text=PROSE,
        kind=ClaimKind.OBSERVED,
        evidence_ids=["ev"],
        output_bindings=[_binding("SERIES_WINNER"), _binding("TOTAL_GAMES")],
    )
    verified = VerifiedClaim(
        claim_index=0,
        claim=claim,
        evidence_ids=["ev"],
        output_bindings=[],
    )
    statuses = [
        OutputFinalStatus(
            requirement_kind="task",
            requirement_id=None,
            output_id=output_id,
            status="missing",
            claim_index=None,
            binding=None,
        )
        for output_id in ("SERIES_WINNER", "TOTAL_GAMES")
    ]
    return SimpleNamespace(
        output_statuses=statuses,
        gaps=[],
        verified_claims=[verified],
        execution=SimpleNamespace(
            evidence=[],
            plan=Plan(
                nodes=[
                    PlanNode(
                        id="n1",
                        description="series",
                        capability_hints=["season_series"],
                    )
                ]
            ),
        ),
    )

def test_verified_prose_suppresses_contradicting_missing_tails() -> None:
    text = _answer_text(_result())
    assert PROSE in text
    assert "SERIES_WINNER could not be verified (missing)." not in text
    assert "TOTAL_GAMES could not be verified (missing)." not in text

def test_genuinely_uncovered_output_still_discloses() -> None:
    result = _result()
    result.output_statuses = [
        *result.output_statuses,
        OutputFinalStatus(
            requirement_kind="task",
            requirement_id=None,
            output_id="UNCOVERED",
            status="missing",
            claim_index=None,
            binding=None,
        ),
    ]
    text = _answer_text(result)
    assert PROSE in text
    assert "UNCOVERED could not be verified (missing)." in text
