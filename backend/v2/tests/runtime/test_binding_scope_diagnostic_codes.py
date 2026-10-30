from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from pydantic_core import PydanticCustomError

from v2.contracts import DraftReport, EvidenceOutputBinding

SENTINEL = "SECRET_SENTINEL_MUST_NOT_LEAK"
MISSING_CODE = "evidence_requirement_id_missing"
PARTIAL_CODE = "binding_subject_scope_partial"
MISSING_MESSAGE = "evidence binding requires requirement id"
PARTIAL_MESSAGE = "binding subject type, id, and selector must be supplied together"
ROUTE = "synthesizer"
SCHEMA_HASH = "8d8baa15d22e434c371d0324d318f3817bc77188573659596e4601fe7909b332"
DRAFT_SCHEMA_HASH = "3b3dd0f5e06afc108844e0e496e970f5ca2e0556f5f5a3c2f0bc91578d9b79e1"

def _binding(**overrides):
    payload = {
        "requirement_kind": "evidence",
        "requirement_id": "ratings",
        "output_id": "NET_RATING",
        "node_id": "ratings",
        "evidence_id": "ev-1",
        "selector": "rows[0].NET_RATING",
        "row_selector": "rows[0]",
        "value": {"kind": "float", "value": 99.9},
        "subject_entity_type": "team",
        "subject_entity_id": "BOS",
        "subject_selector": "rows[0].TEAM_ID",
        "unit": {"kind": "declared", "value": "points_per_100_possessions"},
        "domain": "team_ratings",
    }
    payload.update(overrides)
    return payload

def _draft(binding):
    return {
        "sections": ["probe"],
        "claims": [{
            "text": "probe",
            "kind": "observed",
            "evidence_ids": ["ev-1"],
            "output_bindings": [binding],
        }],
    }

def _rejection(binding) -> ValidationError:
    with pytest.raises(ValidationError) as caught:
        DraftReport.model_validate(_draft(binding))
    return caught.value

def _schema_hash(schema) -> str:
    document = json.dumps(
        schema.model_json_schema(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(document.encode()).hexdigest()

def _missing_requirement_id():
    binding = _binding()
    del binding["requirement_id"]
    return binding

def _partial_subject_scope():
    binding = _binding()
    del binding["subject_entity_type"]
    del binding["subject_entity_id"]
    del binding["subject_selector"]
    return binding

def test_evidence_requirement_id_missing_has_stable_reason_code():
    error = _rejection(_missing_requirement_id()).errors(
        include_url=False, include_context=False, include_input=False)[0]
    assert error["type"] == MISSING_CODE
    assert error["loc"] == ("claims", 0, "output_bindings", 0, "evidence")
    assert MISSING_MESSAGE in error["msg"]

def test_binding_subject_scope_partial_has_stable_reason_code():
    error = _rejection(_partial_subject_scope()).errors(
        include_url=False, include_context=False, include_input=False)[0]
    assert error["type"] == PARTIAL_CODE
    assert error["loc"] == ("claims", 0, "output_bindings", 0, "evidence")
    assert PARTIAL_MESSAGE in error["msg"]

def test_valid_and_task_bindings_keep_acceptance_and_schema():
    valid = EvidenceOutputBinding.model_validate(_binding())
    assert valid.requirement_id == "ratings"
    task = EvidenceOutputBinding.model_validate(
        _binding(requirement_kind="task", requirement_id="ratings"))
    assert task.requirement_id is None
    assert _schema_hash(EvidenceOutputBinding) == SCHEMA_HASH
    assert _schema_hash(DraftReport) == DRAFT_SCHEMA_HASH
