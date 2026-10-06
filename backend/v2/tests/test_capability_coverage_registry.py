import inspect
import re
from pathlib import Path

import duckdb

from shared import store
from shared.tools import v1_tools
from v2.adapters import coverage
from v2.adapters.capabilities import CAPABILITIES
from v2.adapters.models import ModelIntake
from v2.contracts import EvidenceRequirement, SeasonRef, TaskSpec
from v2.runtime.assembly import capability_catalog

TOOL_MODULES = {tool.name: tool for tool in v1_tools}
SEASON_SCOPED = tuple(
    name for name, spec in CAPABILITIES.items() if spec.task_season_scoped)

def _tool_sources() -> str:
    root = Path(inspect.getfile(store)).parent / "tools"
    return "\n".join(
        path.read_text() for path in sorted(root.glob("*.py"))) \
        + "\n" + inspect.getsource(coverage)

def test_every_capability_names_a_registered_tool():
    unregistered = sorted(
        name for name, spec in CAPABILITIES.items()
        if spec.tool_name not in TOOL_MODULES
        and not callable(getattr(coverage, spec.tool_name, None))
    )
    assert not unregistered, f"unregistered tools: {unregistered}"

def _seasonless_evidence_task(season: str) -> TaskSpec:
    return TaskSpec(
        goal="Cap space for the roster",
        mode="quick",
        deliverable="answer",
        season=SeasonRef(value=season, source="user", confidence=1.0),
        required_evidence=["contracts"],
        requirements=[EvidenceRequirement(
            id="cap",
            description="Cap ledger",
            capability_options=["contracts"],
            capability_arguments={"season": season},
        )],
    )

def test_wire_catalog_offers_every_capability_the_registry_covers():
    assert set(CAPABILITIES) <= set(capability_catalog())

def test_season_scoped_capability_names_coverage_tables():
    blind = {
        name for name in SEASON_SCOPED
        if not (coverage.tables_for_capability(name, {})
                or coverage.declared_tables_for_capability(name, {}))
    }
    assert not blind, (
        "capabilities season coverage cannot see, so intake blames "
        f"silver_boxscores for them: {sorted(blind)}")

def test_registry_never_names_a_non_season_scoped_capability():
    stray = sorted(set(coverage.CAPABILITY_TABLES) - set(SEASON_SCOPED))
    assert not stray, f"entries for capabilities no season can gate: {stray}"

def test_named_tables_are_warehouse_tables_the_tool_layer_reads():
    warehouse = store.tables()
    sources = _tool_sources()
    invented: dict[str, list[str]] = {}
    for name in SEASON_SCOPED:
        for table in coverage.tables_for_capability(name, {}):
            if table in warehouse:
                continue
            if re.search(rf"\b{re.escape(table)}\b", sources) is None:
                invented.setdefault(name, []).append(table)
    assert not invented, f"registry names tables no tool reads: {invented}"

def test_registry_tables_carry_a_season_column_in_the_warehouse():
    connection = duckdb.connect(str(store.DB_PATH), read_only=True)
    try:
        warehouse = store.tables()
        without_season = {
            name: table
            for name in SEASON_SCOPED
            for table in coverage.tables_for_capability(name, {})
            if table in warehouse and not any(
                row[1] == "_season" for row in connection.execute(
                    f"PRAGMA table_info({table})").fetchall())
        }
    finally:
        connection.close()
    assert not without_season, (
        f"registry names tables that hold no season: {without_season}")

def test_capability_with_no_season_source_leaves_the_task_alone():
    task = _seasonless_evidence_task("2015-16")
    assert ModelIntake._mark_uncovered_season(task) == task

def _scratch_warehouse(tmp_path):
    path = tmp_path / "scratch.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute(
        'CREATE TABLE silver_team_games ('
        '_season VARCHAR, Team_ID BIGINT)')
    connection.execute(
        "INSERT INTO silver_team_games VALUES "
        "('2023-24', 1), ('2025-26', 10), ('2025-26', 11), ('2025-26', 12)")
    connection.close()
    return path

def test_league_seasons_excludes_a_season_slice_that_is_one_team(
    tmp_path, monkeypatch):
    from shared import store
    path = _scratch_warehouse(tmp_path)
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "CANONICAL_DB_PATH", path)
    coverage.coverage_cache_clear()
    assert coverage.league_seasons("silver_team_games", "Team_ID", 3) == (
        "2025-26",)

def test_league_seasons_rejects_a_table_or_column_it_cannot_quote(
    tmp_path, monkeypatch):
    from shared import store
    path = _scratch_warehouse(tmp_path)
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "CANONICAL_DB_PATH", path)
    coverage.coverage_cache_clear()
    assert coverage.league_seasons("nope; drop table x", "Team_ID", 3) == ()
    assert coverage.league_seasons(
        "silver_team_games", 'Team_ID" FROM x --', 3) == ()
