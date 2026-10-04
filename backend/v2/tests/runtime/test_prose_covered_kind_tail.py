from __future__ import annotations

from types import SimpleNamespace

from v2.api.routes import _answer_text
from v2.contracts import (
    Claim,
    ClaimKind,
    EvidenceOutputBinding,
    Gap,
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


def _result(*gap_kinds: str) -> SimpleNamespace:
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
        gaps=[Gap(kind=kind, message="gap") for kind in gap_kinds],
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


def test_prose_covered_outputs_suppress_unpublished_tail() -> None:
    text = _answer_text(_result("synthesis_incomplete"))
    assert PROSE in text
    assert "Some requested outputs could not be published." not in text


def test_prose_covered_outputs_suppress_unverified_tail() -> None:
    text = _answer_text(_result("missing_evidence"))
    assert PROSE in text
    assert "Some requested outputs could not be verified." not in text


def test_genuinely_uncovered_output_keeps_kind_tail() -> None:
    result = _result("synthesis_incomplete")
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
    assert "Some requested outputs could not be published." in text
    assert "UNCOVERED could not be verified (missing)." in text
