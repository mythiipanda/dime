from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from pydantic_core import PydanticCustomError

from v2.adapters import models
from v2.adapters.models import (
    SAFE_FAILURE_VALIDATION_SUBTYPES,
    SAFE_PYDANTIC_ERROR_TYPES,
    ProviderStructuredModel,
)
from v2.contracts import DraftReport, EvidenceOutputBinding
from v2.runtime import LedgerEntry
from v2.runtime.ledger import _validate_assistant_attempt

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

@pytest.mark.parametrize(("binding", "code"), [
    (_missing_requirement_id(), MISSING_CODE),
    (_partial_subject_scope(), PARTIAL_CODE),
])
def test_adapter_taxonomy_names_each_binding_reason_code(binding, code):
    taxonomy = ProviderStructuredModel._safe_failure_taxonomy(
        _rejection(binding), schema=DraftReport, route=ROUTE)
    assert taxonomy["failure_phase"] == "json_or_schema_validation"
    assert taxonomy["failure_validation_subtype"] == code
    assert taxonomy["failure_validation_errors"] == [
        {"type": code,
         "loc": ["claims", "<unknown-field>", "output_bindings",
                 "<unknown-field>", "<unknown-field>"]}]
    assert code in SAFE_PYDANTIC_ERROR_TYPES
    assert code in SAFE_FAILURE_VALIDATION_SUBTYPES
    encoded = json.dumps(taxonomy)
    assert SENTINEL not in encoded
    assert "ratings" not in encoded
    assert "rows[0]" not in encoded

def _attempt_item(taxonomy, *, error_type=None, subtype=None):
    return {
        "route": ROUTE,
        "provider": "inception",
        "model": "mercury-2.5",
        "attempt_number": 1,
        "exception_type": "UnexpectedModelBehavior",
        "message_class": "structured_output",
        "latency_ms": 1,
        "failure_top_class": taxonomy["failure_top_class"],
        "failure_class_chain": taxonomy["failure_class_chain"],
        "failure_phase": taxonomy["failure_phase"],
        "failure_validation_errors": (
            [{"type": error_type, "loc": ["claims", 0, "output_bindings", 0]}]
            if error_type else taxonomy["failure_validation_errors"]),
        "failure_validation_subtype": subtype or taxonomy["failure_validation_subtype"],
        "failure_schema_sha256": taxonomy["failure_schema_sha256"],
        "failure_route": taxonomy["failure_route"],
    }

def _assistant_attempt(item):
    return {"status": "failed", "error": "bounded", "provider_attempts": [item]}

@pytest.mark.parametrize(("binding", "code"), [
    (_missing_requirement_id(), MISSING_CODE),
    (_partial_subject_scope(), PARTIAL_CODE),
])
def test_real_ledger_boundary_accepts_each_binding_reason_code(binding, code):
    taxonomy = ProviderStructuredModel._safe_failure_taxonomy(
        _rejection(binding), schema=DraftReport, route=ROUTE)
    item = _attempt_item(taxonomy)
    _validate_assistant_attempt(_assistant_attempt(item))
    assert item["failure_validation_errors"][0]["type"] == code
    assert item["failure_validation_subtype"] == code

def test_real_ledger_boundary_rejects_unknown_validation_type():
    dynamic = ValidationError.from_exception_data("DraftReport", [{
        "type": PydanticCustomError(SENTINEL, SENTINEL),
        "loc": ("claims", 0, "output_bindings", 0),
        "input": SENTINEL,
    }])
    taxonomy = ProviderStructuredModel._safe_failure_taxonomy(
        dynamic, schema=DraftReport, route=ROUTE)
    item = _attempt_item(taxonomy, error_type=SENTINEL,
                         subtype="other_contract_invariant")
    with pytest.raises(ValueError):
        _validate_assistant_attempt(_assistant_attempt(item))

@pytest.mark.parametrize("code", [MISSING_CODE, PARTIAL_CODE])
def test_unregistered_reason_code_fails_real_ledger_boundary(monkeypatch, code):
    taxonomy = ProviderStructuredModel._safe_failure_taxonomy(
        _rejection(_missing_requirement_id() if code == MISSING_CODE
                   else _partial_subject_scope()),
        schema=DraftReport, route=ROUTE)
    item = _attempt_item(taxonomy)
    monkeypatch.setattr(models, "SAFE_PYDANTIC_ERROR_TYPES",
                        SAFE_PYDANTIC_ERROR_TYPES - {code})
    with pytest.raises(ValueError):
        _validate_assistant_attempt(_assistant_attempt(item))
    monkeypatch.undo()
    monkeypatch.setattr(models, "SAFE_FAILURE_VALIDATION_SUBTYPES",
                        SAFE_FAILURE_VALIDATION_SUBTYPES - {code})
    with pytest.raises(ValueError):
        _validate_assistant_attempt(_assistant_attempt(item))

def test_marker_sentinel_is_redacted_then_accepted_by_real_ledger():
    rejection = _rejection(_binding(**{SENTINEL: SENTINEL}))
    taxonomy = ProviderStructuredModel._safe_failure_taxonomy(
        rejection, schema=DraftReport, route=ROUTE)
    assert taxonomy["failure_validation_errors"][0]["type"] == "extra_forbidden"
    assert SENTINEL not in json.dumps(taxonomy)
    item = _attempt_item(taxonomy)
    _validate_assistant_attempt(_assistant_attempt(item))
    entry = LedgerEntry(
        sequence=1, run_id="run", kind="assistant/attempt",
        recorded_at=datetime.now(UTC), turn_id="run", call_id="model:1",
        data=_assistant_attempt(item))
    encoded = json.dumps(entry.model_dump(mode="json"))
    assert SENTINEL not in encoded

def test_unknown_validator_error_stays_redacted():
    dynamic = ValidationError.from_exception_data("DraftReport", [{
        "type": PydanticCustomError(SENTINEL, SENTINEL),
        "loc": ("claims", 0, "output_bindings", 0),
        "input": SENTINEL,
    }])
    taxonomy = ProviderStructuredModel._safe_failure_taxonomy(
        dynamic, schema=DraftReport, route=ROUTE)
    assert taxonomy["failure_validation_errors"] == [
        {"type": "<unknown-error-type>",
         "loc": ["claims", "<unknown-field>", "output_bindings",
                 "<unknown-field>"]}]
    assert taxonomy["failure_validation_subtype"] == "other_contract_invariant"
    assert SENTINEL not in json.dumps(taxonomy)
