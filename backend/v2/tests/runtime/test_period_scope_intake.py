import pytest

from v2.contracts import TaskSpec


def test_scope_defaults_for_existing_callers_and_is_hidden_from_model_schema():
    task = TaskSpec(goal="record", mode="quick", deliverable="record")
    schema = TaskSpec.model_json_schema()
    assert task.period_scope == "unspecified"
    assert task.period_scope_source == "default"
    assert "period_scope" in TaskSpec.model_fields
    assert "period_scope_source" in TaskSpec.model_fields
    assert "period_scope" not in schema["properties"]
    assert "period_scope_source" not in schema["properties"]
    assert "period_scope" not in schema.get("required", [])
    assert "period_scope_source" not in schema.get("required", [])


@pytest.mark.parametrize(("scope", "source"), [
    ("regular_season", "default"),
    ("unspecified", "explicit_request"),
])
def test_period_scope_provenance_must_match(scope, source):
    with pytest.raises(ValueError, match="period scope source"):
        TaskSpec(
            goal="record",
            mode="quick",
            deliverable="record",
            period_scope=scope,
            period_scope_source=source,
        )


@pytest.fixture
def anyio_backend():
    return "asyncio"
