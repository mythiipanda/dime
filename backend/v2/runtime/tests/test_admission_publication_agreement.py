from __future__ import annotations

import shutil
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

FIXTURES = BACKEND / "tests" / "fixtures" / "bbref_awards"
SEASON = "2023-24"
AS_OF = date(2026, 9, 8)



def _flat_envelope():
    from v2.contracts import EntityRef, EvidenceEnvelope

    team = EntityRef(id="1610612738", type="team", display_name="North Bay Kings")
    return EvidenceEnvelope(
        evidence_id="evidence:flat",
        capability="matchup_brief",
        source="silver_team_ratings:fetch_matchup:warehouse",
        observed_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
        season="2024-25",
        as_of=date(2026, 9, 8),
        entities=[team],
        rows=[{"TEAM_ID": 1610612738, "OFF_RATING": 116.6}],
        units={"OFF_RATING": "points_per_100_possessions"},
        source_identity={"kind": "warehouse", "warehouse_id": "frozen-eval",
                          "sha256": "a" * 64},
    )


def test_reanchor_consults_shared_selector_instead_of_exact_path():
    import v2.runtime.models as models_module

    seen = []
    real = models_module.resolve_selector

    def spy(envelope, selector, **kwargs):
        seen.append(selector)
        return real(envelope, selector, **kwargs)

    monkey = pytest.MonkeyPatch()
    monkey.setattr(models_module, "resolve_selector", spy)
    try:
        from v2.contracts import EvidenceOutputBinding
        from v2.runtime.models import _reanchor_binding

        envelope = _flat_envelope()
        envelope = envelope.model_copy(update={
            "rows": [
                {"TEAM_ID": 999, "OFF_RATING": 100.0},
                {"TEAM_ID": 1610612738, "OFF_RATING": 116.6},
            ],
        })
        binding = EvidenceOutputBinding(
            requirement_kind="task", requirement_id=None, output_id="OFF_RATING",
            node_id="flat", evidence_id=envelope.evidence_id,
            selector="rows[0].OFF_RATING", row_selector="rows[0]",
            subject_entity_type="team", subject_entity_id="1610612738",
            subject_selector="rows[0].TEAM_ID",
            value={"kind": "float", "value": 116.6},
            unit={"kind": "declared", "value": "points_per_100_possessions"},
            domain="matchup_brief")
        _reanchor_binding(binding, envelope)
        assert seen, "reanchor must consult the shared selector"
        assert "rows[1].OFF_RATING" in seen
    finally:
        monkey.undo()
