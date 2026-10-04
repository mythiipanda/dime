import duckdb
import pytest

from shared import store
from v2.adapters import coverage
from v2.adapters.capabilities import CAPABILITIES
from v2.adapters.models import ModelIntake
from v2.contracts import EvidenceRequirement, SeasonRef, TaskSpec

SEASON_SCOPED = tuple(
    name for name, spec in CAPABILITIES.items() if spec.task_season_scoped)


def warehouse_tables(path) -> frozenset:
    connection = duckdb.connect(str(path), read_only=True)
    try:
        return frozenset(
            row[0] for row in connection.execute("SHOW TABLES").fetchall())
    finally:
        connection.close()


def on_hand_tables() -> frozenset:
    return warehouse_tables(coverage.warehouse_path())


def busiest_season() -> str:
    seasons = set()
    for table in sorted(on_hand_tables()):
        seasons |= set(coverage.table_seasons(table))
    ordered = sorted(
        seasons, key=lambda season: coverage.parse_season_start(season) or 0)
    assert ordered, "the warehouse holds no season on any table"
    return ordered[-1]


def task_for(capability: str, season: str) -> TaskSpec:
    return TaskSpec(
        goal=f"Answer from {capability}",
        mode="quick",
        deliverable="answer",
        season=SeasonRef(value=season, source="user", confidence=1.0),
        required_evidence=[capability],
        requirements=[EvidenceRequirement(
            id="evidence",
            description=f"{capability} evidence",
            capability_options=[capability],
            capability_arguments={"season": season},
        )],
    )


@pytest.fixture()
def pointed(monkeypatch):
    def point(path) -> None:
        monkeypatch.setattr(coverage, "warehouse_path", lambda: path)
        coverage.coverage_cache_clear()

    yield point
    coverage.coverage_cache_clear()


def test_the_registry_names_only_tables_a_tool_really_reads():
    from scripts.capability_table_inventory import build, unread_declarations

    assert not unread_declarations(build()), (
        "the registry names tables no tool reads, so coverage is wired to a "
        "table nobody can read")


def test_season_coverage_never_reads_a_table_the_warehouse_lacks():
    on_hand = on_hand_tables()
    phantom = {
        name: sorted(
            table for table in coverage.tables_for_capability(name, {})
            if table not in on_hand)
        for name in SEASON_SCOPED
    }
    phantom = {name: tables for name, tables in phantom.items() if tables}
    assert not phantom, (
        "capabilities wired to tables this warehouse does not have, so a "
        f"season verdict rests on a table nobody can read: {phantom}")


def test_the_selection_path_reaches_every_capability_without_inventing_a_table():
    season = busiest_season()
    for name in SEASON_SCOPED:
        labeled = coverage.task_coverage_groups_labeled(task_for(name, season))
        assert labeled, name
        for label, group in labeled:
            assert label == name, (name, label)
            assert set(group) == set(
                coverage.declared_tables_for_capability(name, {})), name


def test_qualified_leaders_never_resolves_to_a_table_the_warehouse_lacks():
    on_hand = on_hand_tables()
    for stat in ("PTS", "REB", "AST", "STL", "BLK", "DREB", "FG_PCT",
                 "TS_PCT", "FG3_PCT"):
        resolved = coverage.tables_for_capability(
            "qualified_leaders", {"stat_category": stat})
        assert set(resolved) <= on_hand, (stat, resolved)
    assert set(coverage.tables_for_capability("qualified_leaders", {})) <= on_hand


def test_every_warehouse_file_carries_the_registry(pointed):
    files = sorted(coverage.warehouse_path().parent.glob("warehouse*.duckdb"))
    assert files, "no warehouse file to check"
    for path in files:
        pointed(path)
        on_hand = warehouse_tables(path)
        for name in SEASON_SCOPED:
            certify = set(coverage.tables_for_capability(name, {}))
            declared = set(coverage.declared_tables_for_capability(name, {}))
            absent = set(coverage.absent_tables_for_capability(name, {}))
            assert certify <= on_hand, f"{path.name} {name}"
            assert certify | absent == declared, f"{path.name} {name}"
            assert not certify & absent, f"{path.name} {name}"
            assert not absent & on_hand, f"{path.name} {name}"


@pytest.fixture()
def warehouse_without(monkeypatch, tmp_path):
    def build(tables) -> object:
        path = tmp_path / "gap.duckdb"
        connection = duckdb.connect(str(path))
        try:
            for table in tables:
                connection.execute(
                    f"CREATE TABLE {table} (_season VARCHAR)")
            connection.execute(
                "INSERT INTO silver_hist_player_seasons VALUES ('2024-25')")
        finally:
            connection.close()
        monkeypatch.setattr(store, "DB_PATH", path)
        monkeypatch.setattr(store, "CANONICAL_DB_PATH", path)
        monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
        store._tables_cache.clear()
        store._pool_evict_all()
        store.warehouse_identity_cache_clear()
        coverage.coverage_cache_clear()
        return path

    yield build
    store._tables_cache.clear()
    store._pool_evict_all()
    store.warehouse_identity_cache_clear()
    coverage.coverage_cache_clear()


def test_a_capability_whose_table_is_absent_is_not_season_covered(
        warehouse_without):
    on_hand = warehouse_without([
        "silver_hist_player_seasons", "silver_team_games"])
    unserved = {
        name: coverage.declared_tables_for_capability(name, {})
        for name in SEASON_SCOPED
    }
    unserved = {
        name: tables for name, tables in unserved.items()
        if tables and not coverage.tables_for_capability(name, {})
    }
    assert unserved, "every capability kept a table it reads"
    season = busiest_season()
    for name, tables in unserved.items():
        for table in tables:
            assert table not in on_hand_tables(), (name, table)
        result = ModelIntake._mark_uncovered_season(task_for(name, season))
        assert result.season.value == season, name
        spoken = [*result.open_questions, *result.assumptions]
        assert spoken, f"{name} reads only tables it does not have"
        joined = " ".join(spoken)
        for table in tables:
            assert table in joined, (name, table)


def test_a_capability_keeps_its_own_coverage_when_only_one_read_is_absent(
        warehouse_without):
    warehouse_without(["silver_hist_player_seasons", "silver_team_games"])
    tables = coverage.tables_for_capability("rookie_leaders", {})
    assert tables == ("silver_hist_player_seasons",)
    assert coverage.absent_tables_for_capability(
        "rookie_leaders", {}) == ("silver_player_season",)
    season = busiest_season()
    assert ModelIntake._mark_uncovered_season(
        task_for("rookie_leaders", season)).open_questions == []


def test_a_tool_reads_no_season_from_a_table_it_does_not_have(
        warehouse_without):
    path = warehouse_without([
        "silver_hist_player_seasons", "silver_team_games"])
    assert coverage.tables_for_capability("rookie_leaders", {}) == (
        "silver_hist_player_seasons",)
    assert coverage.absent_tables_for_capability(
        "rookie_leaders", {}) == ("silver_player_season",)
    from shared.tools import league

    result = league.get_team_four_factors.invoke(
        {"team": "", "season": "2025-26"})
    assert result["ok"] is False
    assert "silver_four_factors_team" in result["error"]
    assert coverage.table_seasons("silver_four_factors_team") == frozenset()
    assert "silver_four_factors_team" not in warehouse_tables(path)