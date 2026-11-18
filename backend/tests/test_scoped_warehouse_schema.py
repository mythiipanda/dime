
import asyncio
import json
import os
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


def test_default_returns_compact_index_with_bounded_scope(warehouse):
    schema = _invoke(_tool(), {})

    assert set(schema) >= {"tables", "catalog_scope"}
    assert schema["ok"] is True
    assert schema["tool"] == "warehouse_schema"
    assert set(schema["tables"]) == set(_DECLARED)
    assert "warehouse_only_table" not in schema["tables"]

    scope = schema["catalog_scope"]
    assert scope["kind"] == "declared_read_only_tables"
    assert scope["exhaustive_warehouse_inventory"] is False
    assert scope["available_table_count"] == 3
    assert scope["returned_table_count"] == 3
    assert scope["negative_claim_scope"] == (
        "returned declared table names, column counts and season spans only")

    for entry in schema["tables"].values():
        assert set(entry) == {"column_count", "seasons"}
        assert isinstance(entry["column_count"], int)
        assert isinstance(entry["seasons"], str)
    assert schema["tables"]["silver_hist_player_seasons"] == {
        "column_count": 4, "seasons": "2090-91..2090-91 (1 season)"}
    assert "season" not in schema["tables"]["silver_hist_player_seasons"]
    assert "RAW_SECRET_ROW" not in json.dumps(schema)
    assert "tables=[...]" in schema["hint"]


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


def test_unscoped_index_is_smaller_than_scoped_columns(warehouse):
    tool = _tool()
    index = json.dumps(_invoke(tool, {})).encode("utf-8")
    scoped = json.dumps(_invoke(tool, {
        "tables": ["silver_hist_player_seasons", "silver_leaders_pts"],
    })).encode("utf-8")

    assert len(index) < len(scoped)


@pytest.mark.parametrize("selection", [
    ["silver_missing"],
    ["silver_leaders_pts", "silver_missing"],
])
def test_unknown_table_names_are_a_boundary_error(warehouse, selection):
    res = _invoke(_tool(), {"tables": selection})
    assert res["ok"] is False
    assert res["tool"] == "warehouse_schema"
    assert "silver_missing" in res["error"]
    assert res["tables"] == {}
    assert res["columns"] == []


def test_empty_selection_is_a_boundary_error(warehouse):
    res = _invoke(_tool(), {"tables": []})
    assert res["ok"] is False
    assert res["tool"] == "warehouse_schema"
    assert "at least one declared table" in res["error"]
    assert res["tables"] == {}
    assert res["columns"] == []


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


def _require_live_warehouse():
    configured = os.environ.get("DIME_WAREHOUSE")
    path = Path(configured) if configured else store.DB_PATH
    if not path.is_file():
        pytest.skip(f"no warehouse at {path}")
    return path


def test_unscoped_live_payload_stays_under_twelve_thousand_characters(monkeypatch):
    path = _require_live_warehouse()
    monkeypatch.setattr(store, "DB_PATH", path)
    _clear_caches()
    result = _invoke(_tool(), {})
    payload = json.dumps(result)

    assert len(payload) < 12000, len(payload)
    assert result["tables"]
    for name, entry in result["tables"].items():
        assert set(entry) == {"column_count", "seasons"}, name
        assert isinstance(entry["column_count"], int), name
        assert isinstance(entry["seasons"], str), name
    assert "tables=[...]" in payload
    assert result["catalog_scope"]["returned_table_count"] == len(result["tables"])


def test_scoped_live_payload_keeps_column_annotations(monkeypatch):
    path = _require_live_warehouse()
    monkeypatch.setattr(store, "DB_PATH", path)
    _clear_caches()
    result = _invoke(_tool(), {"tables": ["silver_leaders_pts"]})
    payload = json.dumps(result)

    columns = result["tables"]["silver_leaders_pts"]
    assert columns["PTS"]["unit"] == "total_points"
    assert columns["PTS"]["note"]
    assert columns["_season"]["season_semantics"]["unit"] == "season_label"
    assert "total_points" in payload
