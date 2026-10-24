import pytest

from v2.adapters.models import ModelIntake
from v2.contracts import TaskSpec


class _Model:
    def __init__(self, task):
        self.task = task
        self.calls = []

    async def generate(self, **call):
        self.calls.append(call)
        return call["schema"].model_validate(self.task)

@pytest.fixture
def anyio_backend():
    return "asyncio"


def _task(period_scope="playoffs", period_scope_source="explicit_request"):
    return {
        "goal": "team record",
        "mode": "quick",
        "deliverable": "record",
        "season": {"value": "2024-25", "source": "user", "confidence": 1.0},
        "period_scope": period_scope,
        "period_scope_source": period_scope_source,
    }


def _intake(model):
    return ModelIntake(
        model,
        provider="stub",
        model_name="stub-model",
        capability_catalog={},
        requirement_review=False,
    )


@pytest.fixture
def no_warehouse_reads(monkeypatch):
    from v2.adapters import coverage

    monkeypatch.setattr(coverage, "table_seasons", lambda table: frozenset())


@pytest.mark.parametrize(("user_request", "expected"), [
    ("Regular season team record", "regular_season"),
    ("Regular-season team record", "regular_season"),
    ("2024-25 regular season, excluding playoffs", "regular_season"),
    ("Regular season, not including playoffs", "regular_season"),
    ("Playoffs, excluding regular season", "playoffs"),
    ("Playoffs, regular season not included", "playoffs"),
    ("Team playoff record", "playoffs"),
    ("Team postseason record", "playoffs"),
    ("Team record across all games", "all"),
    ("All games including postseason", "all"),
    ("Team record", "unspecified"),
])
@pytest.mark.anyio
async def test_intake_binds_server_scope_through_normalization(
    user_request, expected, no_warehouse_reads,
):
    forged_scope = "playoffs" if expected != "playoffs" else "regular_season"
    model = _Model(_task(forged_scope, "explicit_request"))
    task = await _intake(model).understand(user_request)
    expected_source = "default" if expected == "unspecified" else "explicit_request"
    assert task.period_scope == expected
    assert task.period_scope_source == expected_source
    assert model.calls[0]["payload"]["period_scope_hint"] == expected
    assert task.open_questions
    assert len(model.calls) == 1


@pytest.mark.parametrize("user_request", [
    "Regular season and playoffs",
    "Not regular season",
    "Excluding playoffs",
    "All games except playoffs",
])
@pytest.mark.anyio
async def test_conflicting_scope_fails_before_model_call(user_request):
    model = _Model(_task())
    with pytest.raises(ValueError, match="conflicting period scopes"):
        await _intake(model).understand(user_request)
    assert model.calls == []


@pytest.mark.anyio
async def test_scope_does_not_come_from_conversation_history(no_warehouse_reads):
    from v2.contracts import ConversationTurn

    model = _Model(_task())
    task = await _intake(model).understand(
        "Team record",
        context=(ConversationTurn(role="user", content="Compare postseason records"),),
    )
    assert task.period_scope == "unspecified"
    assert task.period_scope_source == "default"


@pytest.mark.anyio
async def test_scope_survives_default_season_and_coverage_copies(
    monkeypatch, no_warehouse_reads,
):
    from shared.tools import _core

    monkeypatch.setattr(_core, "last_completed_season", lambda: "2024-25")
    model = _Model({
        "goal": "team record",
        "mode": "quick",
        "deliverable": "record",
        "period_scope": "playoffs",
        "period_scope_source": "explicit_request",
    })
    task = await _intake(model).understand("Regular season team record")
    assert task.period_scope == "regular_season"
    assert task.period_scope_source == "explicit_request"
    assert task.season is not None and task.season.source == "default"
    assert task.open_questions


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
