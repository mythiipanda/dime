from datetime import UTC, datetime

import pytest

from v2.adapters.capabilities import CAPABILITIES, COUNT, FRACTION, MINUTES, PER_GAME
from v2.adapters.core import build_envelope
from v2.contracts import (
    Claim,
    ClaimSource,
    DraftReport,
    EntityRef,
    EvidenceOutputBinding,
    Plan,
    PlanNode,
    TaskSpec,
    VerifiedClaim,
)
from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings

_PLAYER_ID = "424242"
_PLAYER_NAME = "QA Fixture Player"
_SEASON = "2024-25"
_PPG = 26.5

_SEASON_LINE = {
    "PLAYER_ID": 424242,
    "PLAYER": _PLAYER_NAME,
    "TEAM": "BOS",
    "AGE": 27,
    "GP": 82,
    "MPG": 35.1,
    "PPG": _PPG,
    "RPG": 7.2,
    "APG": 5.1,
    "SPG": 1.2,
    "BPG": 0.6,
    "FG_PCT": 0.471,
    "FG3_PCT": 0.382,
    "FT_PCT": 0.855,
    "TS_PCT": 0.601,
}

_EXPECTED_UNITS = {
    "GP": COUNT,
    "MPG": MINUTES,
    "PPG": PER_GAME,
    "RPG": PER_GAME,
    "APG": PER_GAME,
    "SPG": PER_GAME,
    "BPG": PER_GAME,
    "FG_PCT": FRACTION,
    "FG3_PCT": FRACTION,
    "FT_PCT": FRACTION,
    "TS_PCT": FRACTION,
}

def _envelope():
    return build_envelope(
        CAPABILITIES["player_report"],
        {"player": _PLAYER_NAME, "season": _SEASON},
        {
            "tool": "get_player_report",
            "ok": True,
            "rows": {"season_line": dict(_SEASON_LINE)},
            "meta": {
                "source": "warehouse",
                "season": _SEASON,
                "warehouse_id": "frozen-eval",
                "warehouse_sha256": "a" * 64,
            },
        },
        observed_at=datetime.now(UTC),
    )

def _task():
    return TaskSpec(
        goal="season scoring average",
        mode="quick",
        deliverable="answer",
        requested_outputs=["PPG"],
        entities=[EntityRef(id=_PLAYER_ID, type="player", display_name=_PLAYER_NAME)],
    )

def _binding(unit_value):
    envelope = _envelope()
    return envelope, EvidenceOutputBinding(
        requirement_kind="task",
        requirement_id=None,
        output_id="PPG",
        node_id="report_node",
        evidence_id=envelope.evidence_id,
        selector="rows.season_line.PPG",
        row_selector="rows.season_line",
        value={"kind": "float", "value": _PPG},
        subject_entity_type="player",
        subject_entity_id=_PLAYER_ID,
        subject_selector="rows.season_line.PLAYER_ID",
        unit={"kind": "declared", "value": unit_value},
        domain="player_report",
    )

def _admit(envelope, binding):
    execution = ExecutionResult(
        plan=Plan(nodes=[PlanNode(
            id="report_node",
            description="season line",
            capability_hints=["player_report"],
            status="complete",
        )]),
        evidence_by_node={"report_node": envelope},
        attempts={"report_node": 1},
    )
    claim = Claim(
        text="verified claim",
        kind="observed",
        evidence_ids=[envelope.evidence_id],
        output_bindings=[binding],
    )
    draft = DraftReport(sections=["claim"], claims=[claim])
    verified = VerifiedClaim(
        claim_index=0,
        claim=claim,
        evidence_ids=[envelope.evidence_id],
        sources=[ClaimSource(
            evidence_id=envelope.evidence_id,
            source=envelope.source,
            capability=envelope.capability,
            observed_at=envelope.observed_at,
        )],
        output_bindings=[binding],
    )
    return admit_verified_claim_bindings(_task(), execution, draft, verified)

def test_envelope_carries_season_line_units():
    assert _envelope().units == _EXPECTED_UNITS

@pytest.mark.parametrize("unit", ["per_game", "per game", "points per game", "rebounds per game", "assists per game", "steals per game", "blocks per game"])
def test_ppg_per_game_binding_admits(unit):
    envelope, binding = _binding(unit)
    admitted = _admit(envelope, binding)
    assert admitted.output_bindings[0].value.value == _PPG

def test_invented_unit_still_rejects():
    envelope, binding = _binding("lightyears")
    with pytest.raises(ValueError):
        _admit(envelope, binding)
