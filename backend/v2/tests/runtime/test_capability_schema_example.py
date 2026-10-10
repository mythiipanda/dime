import json
import pytest
from pydantic import ValidationError
from v2.arguments import CapabilityArgumentSet

DESCRIPTION = CapabilityArgumentSet.model_json_schema()['description']


def _correct_example():
    marker = 'Correct: '
    start = DESCRIPTION.index(marker) + len(marker)
    decoded, _ = json.JSONDecoder().raw_decode(DESCRIPTION[start:])
    return decoded


def test_correct_example_matches_model_shape():
    example = _correct_example()
    assert example == {
        'capability_id': 'standings',
        'arguments': {
            'entries': [{'key': 'season', 'kind': 'string', 'string_value': '2025-26'}]
        },
    }
    validated = CapabilityArgumentSet.model_validate(example)
    assert validated.capability_id == 'standings'
    assert validated.arguments.as_dict()['season'] == '2025-26'


def test_old_entries_only_outer_shape_rejected():
    with pytest.raises(ValidationError):
        CapabilityArgumentSet.model_validate(
            {'entries': [{'key': 'season', 'kind': 'string', 'string_value': '2025-26'}]}
        )


def test_flat_nested_arguments_rejected():
    with pytest.raises(ValidationError):
        CapabilityArgumentSet.model_validate(
            {'capability_id': 'standings', 'arguments': {'season': '2025-26'}}
        )


def test_extra_outer_keys_rejected():
    with pytest.raises(ValidationError):
        CapabilityArgumentSet.model_validate(
            {
                'capability_id': 'standings',
                'arguments': {
                    'entries': [{'key': 'season', 'kind': 'string', 'string_value': '2025-26'}]
                },
                'bogus': 1,
            }
        )


def test_duplicate_nested_keys_rejected():
    with pytest.raises(ValidationError):
        CapabilityArgumentSet.model_validate(
            {
                'capability_id': 'standings',
                'arguments': {
                    'entries': [
                        {'key': 'season', 'kind': 'string', 'string_value': '2025-26'},
                        {'key': 'season', 'kind': 'string', 'string_value': '2026-27'},
                    ]
                },
            }
        )
