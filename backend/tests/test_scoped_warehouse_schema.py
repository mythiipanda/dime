"""Scoped declared-table selection at the python_tools catalogue boundary."""

import asyncio
import json
import sys
from pathlib import Path

import duckdb
import pytest
from pydantic import ValidationError

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "analyst"))

from analyst import python_tools  # noqa: E402
from shared import store  # noqa: E402
from shared.tools import league  # noqa: E402

_DECLARED = (
    "silver_hist_player_seasons",
    "silver_leaders_pts",
    "silver_boxscores",
)


def _make_warehouse(db: Path) -> None:
    bulk = ", ".join(f"metadata_{index} DOUBLE" for index in range(1200))
    con = duckdb.connect(str(db))
    try:
        con.execute(
            "CREATE TABLE silver_hist_player_seasons ("
            "season INTEGER, _season VARCHAR, PTS DOUBLE, _source VARCHAR)")
        con.execute(
            "INSERT INTO silver_hist_player_seasons VALUES "
            "(2091, '2090-91', 11.8, 'owned-synthetic')")
        con.execute(
            "CREATE TABLE silver_leaders_pts ("
            "_season VARCHAR, PTS INTEGER, _source VARCHAR, "
            "RAW_SECRET_ROW VARCHAR)")
        con.execute(
            "INSERT INTO silver_leaders_pts VALUES "
            "('2090-91', 71, 'owned-synthetic', 'synthetic-only')")
        con.execute(
            f"CREATE TABLE silver_boxscores (_season VARCHAR, PTS INTEGER, {bulk})")
        con.execute("CREATE TABLE warehouse_only_table (secret DOUBLE)")
    finally:
        con.close()


def _clear_caches() -> None:
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()
    store.warehouse_identity_cache_clear()
    league._clear_warehouse_schema_cache()


@pytest.fixture()
def warehouse(monkeypatch, tmp_path):
    db = tmp_path / "warehouse.duckdb"
    _make_warehouse(db)
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    _clear_caches()
    yield db
    _clear_caches()


def _invoke(tool, arguments: dict):
    return asyncio.run(tool.ainvoke(arguments))


def _tool() -> object:
    return python_tools.catalogue()["warehouse_schema"]


def test_default_returns_full_declared_schema_with_bounded_scope(warehouse):
    schema = _invoke(_tool(), {})

    assert list(schema) == ["tables", "catalog_scope"]
    assert set(schema["tables"]) == set(_DECLARED)
    assert "warehouse_only_table" not in schema["tables"]

    scope = schema["catalog_scope"]
    assert scope["kind"] == "declared_read_only_tables"
    assert scope["exhaustive_warehouse_inventory"] is False
    assert scope["available_table_count"] == 3
    assert scope["returned_table_count"] == 3
    assert scope["negative_claim_scope"] == (
        "returned declared tables and columns only")

    seasons = schema["tables"]["silver_hist_player_seasons"]
    assert seasons["season"]["type"] == "INTEGER"
    assert seasons["season"]["season_semantics"]["encoding"] == "end_year_numeric"
    assert seasons["_season"]["season_semantics"]["encoding"] == "canonical_label"
    assert seasons["PTS"]["unit"] == "points_per_game"
    assert schema["tables"]["silver_leaders_pts"]["PTS"]["unit"] == "total_points"
    assert "RAW_SECRET_ROW" in schema["tables"]["silver_leaders_pts"]


def test_selection_returns_only_requested_declared_tables_with_metadata(warehouse):
    scoped = _invoke(_tool(), {
        "tables": ["silver_hist_player_seasons", "silver_leaders_pts"]})

    assert list(scoped["tables"]) == [
        "silver_hist_player_seasons", "silver_leaders_pts"]
    assert "silver_boxscores" not in scoped["tables"]

    seasons = scoped["tables"]["silver_hist_player_seasons"]
    assert seasons["season"]["type"] == "INTEGER"
    assert seasons["season"]["season_semantics"]["encoding"] == "end_year_numeric"
    assert seasons["_season"]["season_semantics"]["encoding"] == "canonical_label"
    assert seasons["PTS"]["unit"] == "points_per_game"
    leaders = scoped["tables"]["silver_leaders_pts"]
    assert leaders["_season"]["season_semantics"]["unit"] == "season_label"
    assert leaders["PTS"]["unit"] == "total_points"

    scope = scoped["catalog_scope"]
    assert scope["available_table_count"] == 3
    assert scope["returned_table_count"] == 2
    assert scope["exhaustive_warehouse_inventory"] is False


def test_selection_deduplicates_without_reordering(warehouse):
    scoped = _invoke(_tool(), {
        "tables": ["silver_leaders_pts", "silver_hist_player_seasons",
                   "silver_leaders_pts"]})

    assert list(scoped["tables"]) == [
        "silver_leaders_pts", "silver_hist_player_seasons"]
    assert scoped["catalog_scope"]["returned_table_count"] == 2


def test_scoped_payload_is_measurably_smaller(warehouse):
    tool = _tool()
    full = json.dumps(_invoke(tool, {})).encode("utf-8")
    scoped = json.dumps(_invoke(tool, {
        "tables": ["silver_hist_player_seasons", "silver_leaders_pts"],
    })).encode("utf-8")

    assert len(scoped) < len(full)


@pytest.mark.parametrize("selection", [
    ["silver_missing"],
    ["silver_leaders_pts", "silver_missing"],
])
def test_unknown_table_names_are_a_boundary_error(warehouse, selection):
    with pytest.raises(ValueError, match="silver_missing"):
        _invoke(_tool(), {"tables": selection})


def test_empty_selection_is_a_boundary_error(warehouse):
    with pytest.raises(ValueError, match="at least one declared table"):
        _invoke(_tool(), {"tables": []})


@pytest.mark.parametrize("arguments", [
    {"tables": "silver_leaders_pts"},
    {"tables": [1]},
    {"tables": {"silver_leaders_pts": True}},
])
def test_invalid_selection_shape_is_rejected(warehouse, arguments):
    with pytest.raises(ValidationError):
        _invoke(_tool(), arguments)


def test_input_schema_makes_tables_an_optional_string_list():
    schema = _tool().args_schema.model_json_schema()
    property_schema = schema["properties"]["tables"]
    variants = property_schema.get("anyOf", [property_schema])

    assert "tables" not in schema.get("required", [])
    assert any(
        variant.get("type") == "array"
        and variant.get("items", {}).get("type") == "string"
        for variant in variants)


def test_sql_exec_contract_is_unchanged(warehouse):
    tool = python_tools.catalogue()["sql_exec"]

    result = _invoke(tool, {"sql": "SELECT PTS FROM silver_hist_player_seasons"})
    assert result["ok"] is True
    assert result["rows"] == [{"PTS": 11.8}]
    assert result["meta"]["tables"] == ["silver_hist_player_seasons"]

    blocked = _invoke(tool, {"sql": "DELETE FROM silver_leaders_pts"})
    assert blocked["ok"] is False
    assert "only SELECT/WITH queries are allowed" in blocked["error"]


def test_warehouse_schema_description_dynamically_lists_authoritative_tables():
    sql_exec_module = sys.modules["shared.tools.sql_exec"]
    authoritative_tables = sql_exec_module.TABLES

    tool = _tool()
    for table_name in authoritative_tables:
        assert table_name in tool.description, (
            f"Expected authoritative table '{table_name}' in tool description")
    assert ", ".join(authoritative_tables) in tool.description
    assert "Declared table allowlist:" in tool.description
    assert "not proof of actual table content" in tool.description


def test_warehouse_schema_description_derived_dynamically_from_registry(monkeypatch):
    sql_exec_module = sys.modules["shared.tools.sql_exec"]

    synthetic_tables = ("silver_custom_alpha", "silver_custom_beta")
    monkeypatch.setattr(sql_exec_module, "TABLES", synthetic_tables)

    tool = python_tools.catalogue()["warehouse_schema"]
    assert "silver_custom_alpha, silver_custom_beta" in tool.description
    assert "silver_standings" not in tool.description
    assert "silver_hist_standings" not in tool.description
