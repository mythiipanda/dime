import pytest


def _seed_warehouse_seasons(tmp_path, monkeypatch, seasons):
    import duckdb

    from shared import store
    from shared.tools import _core as core_mod
    from v2.adapters import coverage as coverage_mod

    db = tmp_path / "warehouse.duckdb"
    connection = duckdb.connect(str(db))
    connection.execute(
        "CREATE TABLE silver_boxscores (_season VARCHAR, GAME_ID VARCHAR)")
    for season in seasons:
        connection.execute(
            "INSERT INTO silver_boxscores VALUES (?, ?)",
            [season, "00200001"])
    connection.close()
    monkeypatch.setattr(store, "DB_PATH", db)
    core_mod.last_completed_season_cache_clear()
    coverage_mod.coverage_cache_clear()
    return db


class StubModel:
    def __init__(self, values):
        self.values = iter(values)

    async def generate(self, **call):
        return call["schema"].model_validate(next(self.values))


def _intake(stub):
    from v2.adapters.models import ModelIntake

    return ModelIntake(
        stub, provider="stub", model_name="stub",
        capability_catalog={"team_ratings": {}})


@pytest.mark.anyio
async def test_resolved_relative_season_survives_without_substitution(
    tmp_path, monkeypatch,
):
    _seed_warehouse_seasons(tmp_path, monkeypatch, ["2024-25"])
    stub = StubModel([{
        "goal": "compare Lakers and Celtics net ratings last season",
        "mode": "quick", "deliverable": "comparison",
        "season": {
            "value": "2025-26", "source": "resolved", "confidence": 0.9,
        },
        "required_evidence": ["team_ratings"],
    }])
    task = await _intake(stub).understand(
        "Compare the Lakers and Celtics net ratings last season")
    assert task.season.value == "2025-26"
    assert any("2025-26" in question for question in task.open_questions)


@pytest.mark.anyio
async def test_default_season_still_pins_warehouse(
    tmp_path, monkeypatch,
):
    _seed_warehouse_seasons(tmp_path, monkeypatch, ["2024-25"])
    stub = StubModel([{
        "goal": "three point leaders", "mode": "quick",
        "deliverable": "leaders",
        "season": {
            "value": "2099-00", "source": "default", "confidence": 0.9,
        },
        "required_evidence": ["team_ratings"],
    }])
    task = await _intake(stub).understand("Who are the three point leaders?")
    assert task.season.value == "2024-25"
    assert task.season.source == "default"
