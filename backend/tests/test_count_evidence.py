import asyncio
import json
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools.count_evidence import basis_for, count_evidence_meta, profile_for

CAP = 25

SCHEMA = """
CREATE TABLE t AS
SELECT * FROM (VALUES
  (1, 'a', 10.0),
  (2, 'a', NULL),
  (2, 'a', 20.0),
  (3, 'b', 30.0),
  (NULL, 'b', 40.0),
  (4, NULL, 50.0)
) AS t(id, grp, metric);
CREATE TABLE big AS SELECT * FROM range(30) AS t(v);
"""


def run_sql(sql: str, cap: int = CAP):
    con = duckdb.connect(":memory:")
    try:
        con.execute(SCHEMA)
        cur = con.execute(sql)
        columns = [d[0] for d in cur.description]
        all_rows = cur.fetchall()
        rows = [dict(zip(columns, row)) for row in all_rows[:cap]]
        return columns, rows, len(all_rows) > cap
    finally:
        con.close()


def test_t1_avg_plus_count_star_promotes_only_count_star():
    sql = "SELECT avg(metric) AS avg_m, count(*) FROM t"
    columns, rows, _ = run_sql(sql)
    result = basis_for(sql, columns)
    assert result == {"status": "ok",
                      "aggregates": [{"index": 1, "kind": "count_star"}]}
    assert "avg" not in json.dumps(result).lower()
    profile = profile_for(columns, rows)
    assert profile["returned_rows"] == 1


def test_t2_group_by_ordinal_maps_to_projection_index():
    sql = "SELECT grp, count(metric) FROM t GROUP BY 1"
    columns, rows, _ = run_sql(sql)
    result = basis_for(sql, columns)
    assert result == {"status": "ok",
                      "aggregates": [{"index": 1, "kind": "count_column",
                                      "column": "metric"}]}


def test_t3_star_projection_fails_closed():
    sql = "SELECT *, count(*) AS c FROM t GROUP BY id, grp, metric"
    columns, _, _ = run_sql(sql)
    assert basis_for(sql, columns) == {"status": "unavailable"}


def test_t4_duplicate_output_names_fail_closed():
    sql = "SELECT count(*) AS n, count(*) AS n FROM t"
    columns, _, _ = run_sql(sql)
    assert basis_for(sql, columns) == {"status": "unavailable"}
    assert profile_for(["n", "n"], [{"n": 1}]) == {"status": "unavailable"}


@pytest.mark.parametrize("sql", [
    "SELECT count(*) FROM t UNION ALL SELECT count(*) FROM t",
    "SELECT count(*) FROM t INTERSECT SELECT count(*) FROM t",
    "SELECT count(*) FROM t EXCEPT SELECT count(*) FROM t",
])
def test_t5_set_ops_fail_closed(sql):
    assert basis_for(sql, ["count_star()"]) == {"status": "unavailable"}


def test_t6_filter_wrapped_count_fails_closed():
    sql = "SELECT count(*) FILTER (WHERE metric IS NOT NULL) FROM t"
    assert basis_for(sql, ["count_star()"]) == {"status": "unavailable"}


def test_t7_window_wrapped_count_fails_closed():
    sql = "SELECT count(*) OVER () FROM t"
    assert basis_for(sql, ["count_star()"]) == {"status": "unavailable"}


def test_t8_arithmetic_count_fails_closed():
    sql = "SELECT count(*) + 1 FROM t"
    assert basis_for(sql, ["(count_star() + 1)"]) == {"status": "unavailable"}


def test_t9_cte_outer_count_promoted_inner_not_leaked():
    sql = "WITH c AS (SELECT count(*) FROM t) SELECT count(*) FROM c"
    result = basis_for(sql, ["count_star()"])
    assert result == {"status": "ok",
                      "aggregates": [{"index": 0, "kind": "count_star"}]}


def test_t10_derived_table_star_fails_closed():
    sql = "SELECT * FROM (SELECT count(*) FROM t) AS s"
    assert basis_for(sql, ["count_star()"]) == {"status": "unavailable"}


def test_t11_list_and_struct_values_no_crash():
    sql = "SELECT [1, 2] AS l, struct_pack(a := 1) AS s, count(*) FROM t"
    columns, rows, _ = run_sql(sql)
    profile = profile_for(columns, rows)
    assert profile["returned_rows"] == 1
    assert profile["columns"]["l"]["non_null"] == 1
    assert profile["columns"]["s"]["non_null"] == 1


def test_t12_nan_and_null_no_distinct_claim_no_crash():
    rows = [{"x": float("nan"), "n": 1}, {"x": None, "n": None}]
    profile = profile_for(["x", "n"], rows)
    assert profile["columns"]["x"]["non_null"] == 1
    assert profile["columns"]["n"]["non_null"] == 1
    assert "distinct" not in json.dumps(profile).lower()


def test_t13_capped_profile_never_exceeds_cap():
    columns, rows, capped = run_sql("SELECT v FROM big ORDER BY v")
    assert capped is True
    profile = profile_for(columns, rows)
    assert profile["returned_rows"] == CAP
    aggregate = run_sql("SELECT count(*) FROM big")
    agg_columns, agg_rows, agg_capped = aggregate
    assert agg_capped is False
    assert agg_rows == [{"count_star()": 30}]
    meta = count_evidence_meta("SELECT count(*) FROM big",
                               agg_columns, agg_rows)
    assert meta["basis"]["aggregates"] == [{"index": 0, "kind": "count_star"}]
    assert meta["profile"]["returned_rows"] == 1


def test_t14_parse_failure_fails_closed_and_payload_untouched():
    rows = [{"n": 3}]
    evidence = count_evidence_meta("GARBAGE %%% NOT SQL ;;;", ["n"], rows)
    assert evidence["basis"] == {"status": "unavailable"}
    assert rows == [{"n": 3}]


def test_t15_empty_rows_profile_zeros():
    profile = profile_for(["a", "b"], [])
    assert profile == {"returned_rows": 0,
                       "scope": "returned_post_cap",
                       "columns": {"a": {"non_null": 0},
                                   "b": {"non_null": 0}}}


def test_t16_tuple_distinct_is_one_composite_value():
    sql = "SELECT count(distinct (id, grp)) FROM t"
    columns, rows, _ = run_sql(sql)
    assert basis_for(sql, columns) == {"status": "ok",
                                       "aggregates": [{"index": 0,
                                                       "kind": "count_distinct",
                                                       "argument": ["id", "grp"]}]}
    assert rows[0][columns[0]] == 5


def test_t16_multiarg_distinct_is_engine_rejected():
    con = duckdb.connect(":memory:")
    try:
        con.execute(SCHEMA)
        with pytest.raises(Exception):
            con.execute("SELECT count(distinct id, grp) FROM t")
    finally:
        con.close()


def test_distinct_expression_is_not_labeled_column():
    sql = "SELECT count(distinct metric * 2) FROM t"
    columns, _, _ = run_sql(sql)
    result = basis_for(sql, columns)
    assert result == {"status": "ok",
                      "aggregates": [{"index": 0,
                                      "kind": "count_distinct",
                                      "argument": ["metric * 2"]}]}


def test_empty_tuple_distinct_fails_closed():
    result = basis_for("SELECT count(distinct ()) FROM t", ["n"])
    assert result == {"status": "unavailable"}


def test_t17_alias_free_count_star():
    result = basis_for("SELECT count(*) FROM t", ["count_star()"])
    assert result == {"status": "ok",
                      "aggregates": [{"index": 0, "kind": "count_star"}]}


def test_count_column_and_count_distinct_single_argument():
    result = basis_for("SELECT count(distinct metric) FROM t", ["n"])
    assert result == {"status": "ok",
                      "aggregates": [{"index": 0, "kind": "count_distinct",
                                      "column": "metric"}]}


def test_count_expression_is_conservatively_count_expr():
    result = basis_for("SELECT count(metric * 2) FROM t", ["n"])
    assert result == {"status": "ok",
                      "aggregates": [{"index": 0, "kind": "count_expr",
                                      "argument": ["metric * 2"]}]}


def test_count_star_of_star_column_fails_closed():
    result = basis_for("SELECT count(t.*) FROM t", ["n"])
    assert result == {"status": "unavailable"}


def test_case_wrapped_count_fails_closed():
    result = basis_for("SELECT CASE WHEN true THEN count(*) END FROM t",
                       ["col0"])
    assert result == {"status": "unavailable"}


def test_non_select_root_values():
    result = basis_for("SELECT count(*) FROM t VALUES (1)", ["a"])
    assert result == {"status": "unavailable"}


def test_values_root_fails_closed():
    result = basis_for("VALUES (1), (2)", ["col0"])
    assert result == {"status": "unavailable"}


def test_empty_column_list_fails_closed():
    assert basis_for("SELECT 1", []) == {"status": "unavailable"}
    assert basis_for("SELECT 1", [None]) == {"status": "unavailable"}


def test_projection_count_mismatch_fails_closed():
    result = basis_for("SELECT count(*) FROM t", ["a", "b"])
    assert result == {"status": "unavailable"}


def _se_module():
    import importlib
    return importlib.import_module("shared.tools.sql_exec")


def test_sql_exec_bridge_attaches_basis_and_survives(monkeypatch):
    se_module = _se_module()

    async def fake_rerun(query):
        return {"tool": "rerun_sql", "ok": True, "columns": ["n"],
                "rows": [{"n": 6}], "sql": query, "capped": False, "ms": 3}

    monkeypatch.setattr(se_module, "rerun_sql", fake_rerun)
    monkeypatch.setattr(se_module, "_get_warehouse_schema",
                        lambda: ([], {}))
    result = asyncio.run(se_module.sql_exec.ainvoke(
        {"sql": "SELECT count(*) FROM some_declared_table"}))
    assert result["ok"] is True
    assert result["meta"]["basis"] == {
        "status": "ok",
        "aggregates": [{"index": 0, "kind": "count_star"}]}
    assert result["meta"]["profile"] == {
        "returned_rows": 1, "scope": "returned_post_cap",
        "columns": {"n": {"non_null": 1}}}


def test_sql_exec_capped_seam_profile_scope_returned_post_cap(monkeypatch):
    se_module = _se_module()

    async def fake_rerun(query):
        return {"tool": "rerun_sql", "ok": True, "columns": ["v"],
                "rows": [{"v": i} for i in range(CAP)],
                "sql": query, "capped": True, "ms": 3}

    monkeypatch.setattr(se_module, "rerun_sql", fake_rerun)
    monkeypatch.setattr(se_module, "_get_warehouse_schema",
                        lambda: ([], {}))
    result = asyncio.run(se_module.sql_exec.ainvoke(
        {"sql": "SELECT v FROM some_declared_table"}))
    assert result["ok"] is True
    assert result["meta"]["capped"] is True
    assert result["meta"]["profile"]["scope"] == "returned_post_cap"
    assert result["meta"]["profile"]["returned_rows"] == CAP


def test_sql_exec_failure_path_untouched(monkeypatch):
    se_module = _se_module()

    async def fake_rerun(query):
        return {"tool": "rerun_sql", "ok": False, "error": "boom"}

    monkeypatch.setattr(se_module, "rerun_sql", fake_rerun)
    result = asyncio.run(se_module.sql_exec.ainvoke({"sql": "SELECT 1"}))
    assert result["ok"] is False
    assert "basis" not in result["meta"]
    assert "profile" not in result["meta"]
