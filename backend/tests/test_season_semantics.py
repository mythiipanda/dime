from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import duckdb
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


@pytest.fixture()
def synthetic_warehouse(monkeypatch, tmp_path):
    warehouse = tmp_path / "season-semantics.duckdb"
    con = duckdb.connect(str(warehouse))
    try:
        con.execute(
            "CREATE TABLE silver_hist_standings ("
            "_season VARCHAR, season INTEGER, season_id VARCHAR, team_name VARCHAR, "
            "wins INTEGER, losses INTEGER, win_pct DOUBLE)"
        )
        con.execute(
            "CREATE TABLE silver_hist_gamelogs ("
            "_season VARCHAR, season INTEGER, season_type VARCHAR, "
            "team_abbreviation VARCHAR, wl VARCHAR, game_id VARCHAR)"
        )
        con.execute(
            "CREATE TABLE silver_salaries (season INTEGER, team VARCHAR, salary BIGINT)"
        )
        con.executemany(
            "INSERT INTO silver_hist_standings VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("2031-32", 2032, "22031", "Cobalt Foxes", 41, 41, 0.500),
                ("2036-37", 2037, "22036", "Amber Merlins", 48, 34, 0.585),
                ("2042-43", 2043, "22042", "Slate Herons", 52, 30, 0.634),
            ],
        )
        con.executemany(
            "INSERT INTO silver_hist_gamelogs VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("2031-32", 2032, "regular-season", "Cobalt", "W", "r-1"),
                ("2031-32", 2032, "regular-season", "Cobalt", "L", "r-2"),
                ("2031-32", 2032, "playoffs", "Cobalt", "W", "p-1"),
            ],
        )
        con.execute(
            "INSERT INTO silver_salaries VALUES (?, ?, ?)",
            (2032, "Cobalt Foxes", 100000000),
        )
    finally:
        con.close()

    from shared import store
    from shared.tools import league

    monkeypatch.setattr(store, "DB_PATH", warehouse)
    store.warehouse_identity_cache_clear()
    store.warehouse_tables_cache_clear()
    league._clear_warehouse_schema_cache()
    yield warehouse
    league._clear_warehouse_schema_cache()


@pytest.fixture()
def wide_synthetic_warehouse(monkeypatch, tmp_path):
    warehouse = tmp_path / "wide-season-semantics.duckdb"
    con = duckdb.connect(str(warehouse))
    leading = [
        "team_city VARCHAR", "team_name VARCHAR", "wins INTEGER",
        "losses INTEGER", "win_pct DOUBLE",
        *(f"filler_{index:02d} INTEGER" for index in range(1, 36)),
    ]
    trailing = [
        "_season VARCHAR", "season_id VARCHAR", "season_type VARCHAR",
        "_source VARCHAR", "_fetched_at VARCHAR",
    ]
    try:
        con.execute(
            "CREATE TABLE silver_hist_standings ("
            + ", ".join([*leading, *trailing]) + ")"
        )
        con.execute(
            "INSERT INTO silver_hist_standings "
            "(team_city, team_name, wins, losses, win_pct, _season, "
            "season_id, season_type, _source, _fetched_at) "
            "VALUES ('Boston', 'Celtics', 51, 31, 0.622, '2021-22', "
            "'22021', 'regular-season', 'synthetic', '2026-10-28')"
        )
    finally:
        con.close()

    from shared import store
    from shared.tools import league

    monkeypatch.setattr(store, "DB_PATH", warehouse)
    store.warehouse_identity_cache_clear()
    store.warehouse_tables_cache_clear()
    league._clear_warehouse_schema_cache()
    yield warehouse
    league._clear_warehouse_schema_cache()


@pytest.fixture()
def unit_synthetic_warehouse(monkeypatch, tmp_path):
    warehouse = tmp_path / "unit-semantics.duckdb"
    con = duckdb.connect(str(warehouse))
    try:
        con.execute(
            "CREATE TABLE silver_hist_player_seasons ("
            "player_id INTEGER, season INTEGER, _season VARCHAR, "
            "gp INTEGER, "
            "PTS DOUBLE, REB DOUBLE, AST DOUBLE)"
        )
        con.execute(
            "INSERT INTO silver_hist_player_seasons VALUES "
            "(42, 2091, '2090-91', 6, 11.8, 2.3, 4.1)"
        )
        con.execute(
            "CREATE TABLE silver_player_season ("
            "PLAYER_ID INTEGER, GP INTEGER, PPG DOUBLE, RPG DOUBLE, "
            "APG DOUBLE)"
        )
        con.execute(
            "INSERT INTO silver_player_season VALUES "
            "(42, 6, 11.8, 2.3, 4.1)"
        )
        con.execute(
            "CREATE TABLE silver_leaders_pts ("
            "PLAYER_ID INTEGER, GP INTEGER, _season VARCHAR, PTS INTEGER, "
            "REB INTEGER, AST INTEGER, _source VARCHAR)"
        )
        con.execute(
            "INSERT INTO silver_leaders_pts VALUES "
            "(42, 6, '2090-91', 71, 14, 25, 'synthetic')"
        )
        for table in ("silver_leaders_reb", "silver_leaders_ast"):
            con.execute(
                f"CREATE TABLE {table} (PLAYER_ID INTEGER, PTS INTEGER, "
                "REB INTEGER, AST INTEGER)"
            )
            con.execute(
                f"INSERT INTO {table} VALUES (42, 71, 14, 25)"
            )
    finally:
        con.close()

    from shared import store
    from shared.tools import league

    monkeypatch.setattr(store, "DB_PATH", warehouse)
    store.warehouse_identity_cache_clear()
    store.warehouse_tables_cache_clear()
    league._clear_warehouse_schema_cache()
    yield warehouse
    league._clear_warehouse_schema_cache()


def run_sql(sql: str) -> dict:
    from shared.tools.sql_exec import sql_exec

    return asyncio.run(sql_exec.ainvoke({"sql": sql}))


def annotate(sql: str | None, rows: list[dict], columns: list[str],
             table: str, schema_columns: list[str]) -> dict:
    from shared.tools.season_semantics import annotate_result, annotate_schema

    schema = annotate_schema({
        "tables": {table: {name: {"type": "VARCHAR", "unit": "", "note": ""}
                           for name in schema_columns}}
    })
    return annotate_result({
        "ok": True,
        "rows": rows,
        "columns": columns,
        "sql": sql,
        "meta": {"tables": [table]},
    }, schema)["season_semantics"]


def test_actual_schema_exposes_season_encodings(synthetic_warehouse) -> None:
    from v2.runtime.assembly import declared_schema_for

    schema = declared_schema_for("sql_exec")
    standings = schema["tables"]["silver_hist_standings"]
    gamelogs = schema["tables"]["silver_hist_gamelogs"]
    salaries = schema["tables"]["silver_salaries"]
    assert standings["_season"]["season_semantics"]["encoding"] == "canonical_label"
    assert standings["season"]["season_semantics"]["encoding"] == "end_year_numeric"
    assert standings["season_id"]["season_semantics"]["encoding"] == "nba_season_id_start_year"
    assert gamelogs["season"]["season_semantics"]["encoding"] == "end_year_numeric"
    assert gamelogs["season_type"]["season_semantics"]["encoding"] == "season_phase"
    assert salaries["season"]["season_semantics"]["ambiguous"] is True


def test_schema_cache_serves_declaration_and_sql_result(synthetic_warehouse) -> None:
    from shared.tools import league
    from v2.runtime.assembly import declared_schema_for

    declared_schema_for("sql_exec")
    before = league._warehouse_schema_cache_info()
    assert before["misses"] == 1

    result = run_sql(
        "SELECT _season FROM silver_hist_standings ORDER BY _season LIMIT 1")
    after = league._warehouse_schema_cache_info()

    assert result["ok"] is True
    assert result["rows"] == [{"_season": "2031-32"}]
    assert after["misses"] == before["misses"]
    assert after["hits"] == before["hits"] + 1


def test_wide_schema_keeps_internal_fields_and_caps_model_display(
        wide_synthetic_warehouse) -> None:
    from shared.tools.league import (
        _describe_warehouse_schema,
        _get_warehouse_schema,
    )
    from v2.runtime.assembly import declared_schema_for

    present, full = _get_warehouse_schema()
    columns = full["silver_hist_standings"]
    assert len(columns) == 45
    assert list(columns)[40:43] == ["_season", "season_id", "season_type"]

    declared = declared_schema_for("sql_exec")
    shown = declared["tables"]["silver_hist_standings"]
    assert len(shown) == 40
    assert all(name in shown for name in (
        "_season", "season_id", "season_type", "_source", "_fetched_at"))
    assert list(shown) == [name for name in columns if name in shown]
    assert declared["column_budget"] == {
        "max_columns_per_table": 40,
        "truncated_tables": {
            "silver_hist_standings": {
                "total_columns": 45,
                "shown_columns": 40,
                "omitted_columns": 5,
            },
        },
    }

    present, full = _get_warehouse_schema()
    assert "silver_hist_standings" in present
    description = _describe_warehouse_schema(full)
    assert "schema truncated: showing 40 of 45 columns; 5 omitted" in description


def test_sql_exec_uses_full_schema_for_hidden_canonical_season(
        wide_synthetic_warehouse) -> None:
    sql = (
        "SELECT _season, season_id, season_type, wins, losses "
        "FROM silver_hist_standings"
    )
    result = run_sql(sql)

    assert result["ok"] is True
    assert result["sql"] == sql
    assert result["columns"] == [
        "_season", "season_id", "season_type", "wins", "losses"]
    assert result["rows"] == [{
        "_season": "2021-22", "season_id": "22021",
        "season_type": "regular-season", "wins": 51, "losses": 31,
    }]
    semantics = result["season_semantics"]
    assert any(
        item["column"] == "_season" and item["attribution_supported"]
        for item in semantics["season_columns"])
    assert any(
        item["column"] == "_season" and item["season_label"] == "2021-22"
        for item in semantics["resolved_labels"])


@pytest.mark.anyio
async def test_model_intake_request_carries_the_real_wide_schema_budget(
        wide_synthetic_warehouse) -> None:
    from v2.adapters.models import ModelIntake
    from v2.runtime.assembly import capability_catalog

    class Capture:
        def __init__(self):
            self.calls = []

        async def generate(self, **call):
            self.calls.append(call)
            return call["schema"].model_validate({
                "goal": "schema boundary",
                "mode": "quick",
                "deliverable": "verified context",
            })

    model = Capture()
    intake = ModelIntake(
        model, provider="stub", model_name="stub",
        capability_catalog=capability_catalog())
    await intake.understand("Inspect the declared SQL schema.")
    payload = model.calls[0]["payload"]
    schema = payload["capability_catalog"]["sql_exec"]["declared_schema"]

    assert schema["column_budget"]["truncated_tables"][
        "silver_hist_standings"] == {
            "total_columns": 45,
            "shown_columns": 40,
            "omitted_columns": 5,
        }
    assert "_season" in schema["tables"]["silver_hist_standings"]
    assert "season_type" in schema["tables"]["silver_hist_standings"]


def test_model_planner_sees_schema_budget_only_for_sql_candidate(
        wide_synthetic_warehouse) -> None:
    from v2.adapters.models import ModelPlanner, catalog_for_wire
    from v2.contracts import EvidenceRequirement, RunMode, TaskSpec
    from v2.runtime.assembly import capability_catalog

    planner = ModelPlanner.__new__(ModelPlanner)
    planner._catalog = dict(capability_catalog())
    planner._wire_catalog = catalog_for_wire(planner._catalog)
    no_sql = TaskSpec(
        goal="mvp", mode=RunMode.QUICK, deliverable="winner",
        requirements=[EvidenceRequirement(
            id="award", description="official MVP result",
            capability_options=["award_results"])])
    with_sql = TaskSpec(
        goal="rates", mode=RunMode.DEEP_DIVE, deliverable="table",
        requirements=[EvidenceRequirement(
            id="rates", description="agent-written rate query",
            capability_options=["sql_exec"])])

    assert "declared_schema" not in planner._catalog_for(no_sql)["sql_exec"]
    declared = planner._catalog_for(with_sql)["sql_exec"]["declared_schema"]
    assert declared["column_budget"]["truncated_tables"][
        "silver_hist_standings"] == {
            "total_columns": 45,
            "shown_columns": 40,
            "omitted_columns": 5,
        }


def test_declared_schema_uses_table_aware_per_game_units(
        unit_synthetic_warehouse) -> None:
    from shared.tools.league import _column_semantics
    from v2.runtime.assembly import declared_schema_for

    schema = declared_schema_for("sql_exec")["tables"]
    hist = schema["silver_hist_player_seasons"]
    assert {
        name: hist[name]["unit"] for name in ("PTS", "REB", "AST")
    } == {
        "PTS": "points_per_game",
        "REB": "rebounds_per_game",
        "AST": "assists_per_game",
    }
    for name in ("PTS", "REB", "AST"):
        assert "per_mode='pergame'" in hist[name]["note"]
        assert "not cumulative totals" in hist[name]["note"]
    assert hist["gp"]["unit"] == "games_played"
    assert "denominator" in hist["gp"]["note"]
    assert hist["player_id"]["unit"] == ""
    assert hist["player_id"]["type"] == "INTEGER"

    player = schema["silver_player_season"]
    assert [player[name]["unit"] for name in ("PPG", "RPG", "APG")] == [
        "points_per_game", "rebounds_per_game", "assists_per_game"]

    leaders = schema["silver_leaders_pts"]
    assert [leaders[name]["unit"] for name in ("PTS", "REB", "AST")] == [
        "total_points", "total_rebounds", "total_assists"]
    for name in ("PTS", "REB", "AST"):
        assert "scripts/seed.py" in leaders[name]["note"]
        assert "PerMode48.default='Totals'" in leaders[name]["note"]
    for table in ("silver_leaders_reb", "silver_leaders_ast"):
        assert [(schema[table][name]["unit"], schema[table][name]["note"])
                for name in ("PTS", "REB", "AST")] == [("", "")] * 3
    assert _column_semantics(
        "silver_hist_player_seasons", "PTS") == _column_semantics(
            "silver_hist_player_seasons", "pts")
    assert _column_semantics(
        "silver_leaders_pts", "AST") == _column_semantics(
            "SILVER_LEADERS_PTS", "ast")


def test_sql_exec_preserves_hist_per_game_values_and_query(
        unit_synthetic_warehouse) -> None:
    sql = (
        "SELECT player_id, PTS, REB, AST FROM silver_hist_player_seasons "
        "WHERE season = 2091"
    )
    result = run_sql(sql)

    assert result["ok"] is True
    assert result["sql"] == sql
    assert result["columns"] == ["player_id", "PTS", "REB", "AST"]
    assert result["rows"] == [{
        "player_id": 42, "PTS": 11.8, "REB": 2.3, "AST": 4.1,
    }]


def test_sql_exec_exposes_cumulative_values_without_rewriting_either_basis(
        unit_synthetic_warehouse) -> None:
    hist_sql = (
        "SELECT player_id, gp, pts, reb, ast FROM silver_hist_player_seasons "
        "WHERE player_id = 42 AND season = 2091"
    )
    totals_sql = (
        "SELECT PLAYER_ID, GP, PTS, REB, AST FROM silver_leaders_pts "
        "WHERE PLAYER_ID = 42 AND _season = '2090-91'"
    )
    hist = run_sql(hist_sql)
    totals = run_sql(totals_sql)

    assert hist["ok"] and hist["sql"] == hist_sql
    assert hist["columns"] == ["player_id", "gp", "PTS", "REB", "AST"]
    assert hist["rows"] == [{
        "player_id": 42, "gp": 6, "PTS": 11.8, "REB": 2.3, "AST": 4.1,
    }]
    assert totals["ok"] and totals["sql"] == totals_sql
    assert totals["columns"] == ["PLAYER_ID", "GP", "PTS", "REB", "AST"]
    assert totals["rows"] == [{
        "PLAYER_ID": 42, "GP": 6, "PTS": 71, "REB": 14, "AST": 25,
    }]
    assert hist["rows"][0]["PTS"] * hist["rows"][0]["gp"] != totals["rows"][0]["PTS"]


def _execute_sql_capability(sql: str):
    from v2.adapters.core import ToolCapability
    from v2.contracts import PlanNode, RunMode, TaskSpec

    capability = ToolCapability("sql_exec")
    task = TaskSpec(
        goal="Read the selected warehouse columns",
        mode=RunMode.QUICK,
        deliverable="Rows with declared source units",
    )
    node = PlanNode(
        id="sql-evidence",
        description="Read selected columns",
        capability_hints=["sql_exec"],
        arguments={"sql": sql},
    )
    return asyncio.run(capability.execute(node, task, []))


def test_sql_capability_carries_proven_column_units_into_evidence(
        unit_synthetic_warehouse) -> None:
    hist_sql = (
        "SELECT player_id, gp, PTS, REB, AST "
        "FROM silver_hist_player_seasons WHERE player_id = 42"
    )
    total_sql = (
        "SELECT PLAYER_ID, GP, PTS, REB, AST "
        "FROM silver_leaders_pts WHERE PLAYER_ID = 42"
    )
    hist = _execute_sql_capability(hist_sql)
    totals = _execute_sql_capability(total_sql)

    assert hist.rows == [{
        "player_id": 42, "gp": 6, "PTS": 11.8, "REB": 2.3, "AST": 4.1,
    }]
    assert hist.execution_arguments["sql"] == hist_sql
    assert {name: hist.units[name] for name in ("PTS", "REB", "AST")} == {
        "PTS": "points_per_game",
        "REB": "rebounds_per_game",
        "AST": "assists_per_game",
    }
    assert "per_mode='pergame'" in hist.metric_definitions["PTS"]
    assert "not cumulative totals" in hist.metric_definitions["PTS"]

    assert totals.rows == [{
        "PLAYER_ID": 42, "GP": 6, "PTS": 71, "REB": 14, "AST": 25,
    }]
    assert totals.execution_arguments["sql"] == total_sql
    assert {name: totals.units[name] for name in ("PTS", "REB", "AST")} == {
        "PTS": "total_points",
        "REB": "total_rebounds",
        "AST": "total_assists",
    }
    assert "PerMode48.default='Totals'" in totals.metric_definitions["PTS"]


def test_sql_capability_preserves_existing_per_game_fields_and_unmapped_leaders(
        unit_synthetic_warehouse) -> None:
    player = _execute_sql_capability(
        "SELECT PPG, RPG, APG FROM silver_player_season WHERE PLAYER_ID = 42"
    )
    assert player.rows == [{"PPG": 11.8, "RPG": 2.3, "APG": 4.1}]
    assert player.units == {
        "PPG": "points_per_game",
        "RPG": "rebounds_per_game",
        "APG": "assists_per_game",
    }

    for table in ("silver_leaders_reb", "silver_leaders_ast"):
        evidence = _execute_sql_capability(
            f"SELECT PTS, REB, AST FROM {table} WHERE PLAYER_ID = 42"
        )
        assert evidence.rows == [{"PTS": 71, "REB": 14, "AST": 25}]
        assert not {"PTS", "REB", "AST"}.intersection(evidence.units)
        assert not {"PTS", "REB", "AST"}.intersection(
            evidence.metric_definitions)


def test_sql_capability_keeps_generic_aggregate_units(
        unit_synthetic_warehouse) -> None:
    evidence = _execute_sql_capability(
        "SELECT COUNT(*) AS n FROM silver_hist_player_seasons"
    )
    assert evidence.rows == [{"n": 1}]
    assert evidence.units == {"n": "count"}
    assert "count" in evidence.metric_definitions["n"]


def test_synthesizer_request_receives_sql_column_units(
        unit_synthetic_warehouse) -> None:
    from v2.adapters.models import ModelSynthesizer
    from v2.contracts import DraftReport, RunMode, TaskSpec

    class Capture:
        payload = None

        async def generate(self, **call):
            self.payload = call["payload"]
            return DraftReport(sections=[], claims=[], gaps=[])

    evidence = _execute_sql_capability(
        "SELECT PTS, REB, AST FROM silver_hist_player_seasons"
    )
    capture = Capture()
    synthesizer = ModelSynthesizer(
        capture, provider="fixture", model_name="capture")
    task = TaskSpec(
        goal="Describe the returned evidence",
        mode=RunMode.QUICK,
        deliverable="Evidence summary",
    )
    asyncio.run(synthesizer.synthesize(task, [evidence]))

    sent_evidence = capture.payload["evidence"][0]
    assert sent_evidence["units"] == {
        "PTS": "points_per_game",
        "REB": "rebounds_per_game",
        "AST": "assists_per_game",
    }
    assert "per_mode='pergame'" in sent_evidence["metric_definitions"]["PTS"]


@pytest.mark.parametrize("sql", [
    "SELECT PTS AS player_points FROM silver_hist_player_seasons",
    "SELECT PTS * 2 AS PTS FROM silver_hist_player_seasons",
    "SELECT SUM(PTS) AS PTS FROM silver_hist_player_seasons",
    "SELECT h.PTS FROM silver_hist_player_seasons h "
    "JOIN silver_leaders_pts l USING (PLAYER_ID)",
    "WITH rates AS (SELECT PTS FROM silver_hist_player_seasons) "
    "SELECT PTS FROM rates",
    "SELECT * FROM silver_hist_player_seasons",
    "SELECT PTS, PTS FROM silver_hist_player_seasons",
    "SELECT PTS FROM silver_hist_player_seasons "
    "UNION ALL SELECT PTS FROM silver_leaders_pts",
])
def test_sql_capability_does_not_guess_units_for_unsupported_projections(
        unit_synthetic_warehouse, sql: str) -> None:
    evidence = _execute_sql_capability(sql)
    assert not {"PTS", "PTS_1", "player_points"}.intersection(evidence.units)
    assert not {"PTS", "PTS_1", "player_points"}.intersection(
        evidence.metric_definitions)


def test_actual_sql_exec_resolves_generic_off_by_one_shape_and_preserves_raw(
        synthetic_warehouse) -> None:
    sql = (
        "SELECT season_id, _season, season, team_name "
        "FROM silver_hist_standings ORDER BY season_id")
    result = run_sql(sql)
    assert result["ok"] is True
    assert result["columns"] == ["season_id", "_season", "season", "team_name"]
    assert result["sql"] == sql
    assert result["rows"][0] == {
        "season_id": "22031", "_season": "2031-32",
        "season": 2032, "team_name": "Cobalt Foxes",
    }
    semantics = result["season_semantics"]
    assert semantics["query_attribution"]["mode"] == "supported"
    labels = {
        str(item["observed"]): item["season_label"]
        for item in semantics["resolved_labels"] if item["column"] == "season_id"
    }
    assert labels == {"22031": "2031-32", "22036": "2036-37", "22042": "2042-43"}
    assert labels["22031"] != "2030-31"
    assert semantics["contradictions"] == []


def test_actual_sql_exec_end_year_and_canonical_agree(synthetic_warehouse) -> None:
    sql = (
        "SELECT season_type, _season, season, COUNT(*) AS rows, "
        "COUNT(DISTINCT game_id) AS distinct_games "
        "FROM silver_hist_gamelogs WHERE _season='2031-32' "
        "GROUP BY season_type, _season, season")
    result = run_sql(sql)
    assert result["ok"] is True
    semantics = result["season_semantics"]
    labels = {
        (item["column"], str(item["observed"])): item["season_label"]
        for item in semantics["resolved_labels"]
    }
    assert labels[("_season", "2031-32")] == "2031-32"
    assert labels[("season", "2032")] == "2031-32"
    columns = {item["column"]: item for item in semantics["season_columns"]}
    assert columns["season_type"]["encoding"] == "season_phase"
    assert semantics["contradictions"] == []


def test_wide_sql_alias_literal_and_duplicate_outputs_stay_unresolved(
        wide_synthetic_warehouse) -> None:
    alias = run_sql(
        "SELECT _season AS season_id FROM silver_hist_standings")
    literal = run_sql(
        "SELECT '2021-22' AS _season FROM silver_hist_standings")
    duplicate = run_sql(
        "SELECT 2021 AS season_id, season_id "
        "FROM silver_hist_standings")

    assert alias["ok"] and alias["season_semantics"]["resolved_labels"] == []
    assert alias["season_semantics"]["season_columns"][0][
        "attribution_supported"] is False
    assert literal["ok"] and literal["season_semantics"]["resolved_labels"] == []
    assert literal["season_semantics"]["season_columns"][0][
        "attribution_supported"] is False
    assert duplicate["ok"]
    assert duplicate["season_semantics"]["resolved_labels"] == []
    assert duplicate["season_semantics"]["query_attribution"][
        "mode"] == "unresolved"


def test_cte_and_join_results_stay_unresolved(synthetic_warehouse) -> None:
    cte = run_sql(
        "WITH standings AS (SELECT season_id FROM silver_hist_standings) "
        "SELECT season_id FROM standings"
    )
    joined = run_sql(
        "SELECT s.season_id FROM silver_hist_standings s "
        "JOIN silver_salaries x ON true"
    )

    for result in (cte, joined):
        assert result["ok"] is True
        assert result["season_semantics"]["query_attribution"]["mode"] == "unresolved"
        assert result["season_semantics"]["resolved_labels"] == []


def test_small_declared_schema_has_no_truncation_notice(
        synthetic_warehouse) -> None:
    from v2.runtime.assembly import declared_schema_for

    declared = declared_schema_for("sql_exec")
    assert declared["column_budget"] == {
        "max_columns_per_table": 40,
        "truncated_tables": {},
    }
    assert list(declared["tables"]["silver_hist_standings"]) == [
        "_season", "season", "season_id", "team_name", "wins",
        "losses", "win_pct",
    ]


def test_actual_duplicate_output_columns_are_unresolved(synthetic_warehouse) -> None:
    result = run_sql(
        "SELECT 2025 AS season, season FROM silver_hist_standings LIMIT 1")
    assert result["ok"] is True
    assert result["columns"] == ["season", "season"]
    assert len(result["rows"]) == 1
    assert set(result["rows"][0]) == {"season"}
    semantics = result["season_semantics"]
    assert semantics["query_attribution"]["mode"] == "unresolved"
    assert semantics["resolved_labels"] == []
    column = semantics["season_columns"][0]
    assert column["attribution_supported"] is False
    assert column["reason"] == "duplicate output column name"


def test_duplicate_output_name_unit_refusal() -> None:
    semantics = annotate(
        "SELECT 2025 AS season, season FROM silver_hist_standings",
        [{"season": 2025}], ["season"], "silver_hist_standings",
        ["season", "season_id"])
    assert semantics["resolved_labels"] == []
    column = semantics["season_columns"][0]
    assert column["attribution_supported"] is False
    assert column["reason"] == "duplicate output column name"


def test_row_index_after_unlabeled_rows() -> None:
    semantics = annotate(
        "SELECT _season, season FROM silver_hist_gamelogs",
        [{"_season": None, "season": None},
         {"_season": "2031-32", "season": 2031}],
        ["_season", "season"], "silver_hist_gamelogs",
        ["_season", "season"])
    assert semantics["contradictions"][0]["row"] == 1


def test_renamed_alias_star_and_missing_sql_are_unresolved() -> None:
    renamed = annotate(
        "SELECT season_id AS season FROM silver_hist_standings",
        [{"season": 22031}], ["season"], "silver_hist_standings",
        ["season", "season_id"])
    star = annotate(
        "SELECT * FROM silver_hist_standings",
        [{"season_id": "22031", "season": 2032}],
        ["season_id", "season"], "silver_hist_standings",
        ["season_id", "season"])
    missing = annotate(
        None, [{"season": 2032}], ["season"], "silver_hist_standings",
        ["season"])
    assert renamed["resolved_labels"] == []
    assert renamed["season_columns"][0]["reason"].startswith("renamed direct alias")
    assert star["resolved_labels"] == []
    assert star["query_attribution"]["mode"] == "unresolved"
    assert missing["resolved_labels"] == []
    assert missing["query_attribution"]["lineage_proven"] is False
    assert "missing SQL text" in missing["ambiguities"][0]["reason"]
