import pytest
from pydantic import ValidationError
from jsonschema import Draft202012Validator
from v2.arguments import CapabilityArgumentSet, RequirementArguments, migrate_legacy_arguments

DESCRIPTION = CapabilityArgumentSet.model_json_schema()['description']
NORMALIZED = ' '.join(DESCRIPTION.lower().split())


def test_description_binds_entries_to_capability_schema():
    assert 'capability argument schema' in NORMALIZED
    assert 'declared' in NORMALIZED and 'key' in NORMALIZED
    assert 'property' in NORMALIZED
    assert 'required' in NORMALIZED and 'one entries item' in NORMALIZED
    assert 'duplicate' in NORMALIZED or 'twice' in NORMALIZED


def test_description_forbids_unknown_and_allows_optional():
    assert 'forbidden' in NORMALIZED
    assert 'no extra keys' in NORMALIZED
    assert 'additionalproperties false' in NORMALIZED
    assert 'may be omitted' in NORMALIZED


def test_description_keeps_entries_shape_guidance():
    assert 'not a flat' in NORMALIZED and '"key": "value"' in NORMALIZED
    assert 'entries' in NORMALIZED and 'kind' in NORMALIZED
    assert '"string_value"' in NORMALIZED
    assert 'value field named after that kind' in NORMALIZED
    assert 'single "entries" array' in NORMALIZED


def test_flat_argument_map_is_rejected():
    with pytest.raises(ValidationError):
        RequirementArguments.model_validate({'season': '2025-26'})
    ok = RequirementArguments.model_validate(
        {'entries': [{'key': 'season', 'kind': 'string', 'string_value': '2025-26'}]}
    )
    assert ok.as_dict() == {'season': '2025-26'}


def test_capability_schema_rejects_extra_key_and_accepts_exact_payload():
    schema = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {'season': {'type': 'string'}, 'week': {'type': 'integer'}},
        'required': ['season'],
    }

    def errors(values):
        return list(Draft202012Validator(schema).iter_errors(values))

    assert migrate_legacy_arguments('season_stats', {'season': '2025-26'}, schema, target='requirement').as_dict() == {
        'season': '2025-26'
    }
    assert errors({'season': '2025-26', 'week': 4}) == []
    assert [e.message for e in errors({'season': '2025-26', 'nonsense': 1})]
    assert [e.message for e in errors({'week': 4})]
