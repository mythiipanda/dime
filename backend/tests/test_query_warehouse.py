"""query_warehouse guardrail tests. Hermetic: tiny warehouse built in tmp_path.

Covers the write-block proofs (INSERT/UPDATE/DROP/COPY and friends),
statement-shape rules, the row cap, the truncation flag, and honest
error kinds. The tool wrapper is exercised too, through langchain's
invoke path.
"""

import sys
import threading
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import query as q
from shared import store


@pytest.fixture()
def tiny_warehouse(tmp_path, monkeypatch):
    db = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(db))
    con.execute(
        "CREATE TABLE silver_standings "
        "(TeamCity VARCHAR, WINS INTEGER, LOSSES INTEGER, _season VARCHAR)"
    )
    con.execute(
        "INSERT INTO silver_standings VALUES "
        "('Oklahoma City', 68, 14, '2025-26'), "
        "('Boston', 61, 21, '2025-26')"
    )
    con.execute("CREATE TABLE silver_team_games (n INTEGER)")
    con.execute(
        "INSERT INTO silver_team_games SELECT range FROM range(600)"
    )
    con.execute("CREATE TABLE bronze_raw (id INTEGER)")
    con.execute("INSERT INTO bronze_raw VALUES (1)")
    con.close()
    # query_warehouse goes through store.connect, which reads DB_PATH
    # at call time, so this redirect covers the core and the tool.
    monkeypatch.setattr(store, "DB_PATH", db)
    return db


def test_select_works(tiny_warehouse):
    out = q.query_warehouse(
        "SELECT TeamCity, WINS FROM silver_standings "
        "WHERE _season = '2025-26' ORDER BY WINS DESC"
    )
    assert out["ok"] is True
    assert out["columns"] == ["TeamCity", "WINS"]
    assert out["rows"][0] == {"TeamCity": "Oklahoma City", "WINS": 68}
    assert out["truncated"] is False
    assert out["meta"]["row_cap"] == 500


def test_with_cte_works(tiny_warehouse):
    # The CTE name in the outer FROM is not a warehouse table; the
    # parser must not mistake it for one.
    out = q.query_warehouse(
        "WITH okc AS (SELECT * FROM silver_standings "
        "WHERE TeamCity = 'Oklahoma City') "
        "SELECT TeamCity, WINS FROM okc"
    )
    assert out["ok"] is True, out.get("error")
    assert out["rows"] == [{"TeamCity": "Oklahoma City", "WINS": 68}]


def test_multi_cte_works(tiny_warehouse):
    out = q.query_warehouse(
        "WITH a AS (SELECT * FROM silver_standings), "
        "b AS (SELECT * FROM a WHERE WINS > 60) "
        "SELECT COUNT(*) AS n FROM b"
    )
    assert out["ok"] is True, out.get("error")
    assert out["rows"] == [{"n": 2}]


@pytest.mark.parametrize("sql", [
    "INSERT INTO silver_standings VALUES ('X', 1, 1, '2025-26')",
    "UPDATE silver_standings SET WINS = 0",
    "DELETE FROM silver_standings",
    "DROP TABLE silver_standings",
    "CREATE TABLE evil (x INTEGER)",
    "ALTER TABLE silver_standings ADD COLUMN x INTEGER",
    "TRUNCATE silver_standings",
    "VACUUM silver_standings",
    "PRAGMA table_info(silver_standings)",
    "COPY silver_standings TO '/tmp/x.csv'",
    "COPY (SELECT 1) TO '/tmp/x.csv'",
    "ATTACH '/tmp/other.db' AS o",
    "DETACH o",
    "INSTALL httpfs",
    "LOAD spatial",
])
def test_writes_blocked(tiny_warehouse, sql):
    out = q.query_warehouse(sql)
    assert out["ok"] is False
    assert "blocked" in out["error"], out["error"]
    # The warehouse is untouched: the blocked write never ran.
    check = q.query_warehouse("SELECT COUNT(*) AS n FROM silver_standings")
    assert check["rows"] == [{"n": 2}]


def test_readonly_connection_cannot_write(tiny_warehouse):
    # Defense in depth, below the parser: even a hand-built connection
    # through the same store path opens the file read-only.
    con = store.connect(read_only=True)
    try:
        with pytest.raises(Exception):
            con.execute("INSERT INTO silver_standings VALUES ('X', 1, 1, 'x')")
    finally:
        con.close()


def test_multi_statement_blocked(tiny_warehouse):
    out = q.query_warehouse("SELECT 1; SELECT 2")
    assert out["ok"] is False
    assert "multiple statements" in out["error"]
    out = q.query_warehouse("SELECT 1; -- DROP TABLE silver_standings")
    assert out["ok"] is False
    assert "multiple statements" in out["error"]


@pytest.mark.parametrize("sql", [
    "EXPLAIN SELECT 1",
    "SHOW TABLES",
    "DESCRIBE silver_standings",
    "SELECT 1; DROP TABLE silver_standings",
])
def test_non_select_blocked(tiny_warehouse, sql):
    out = q.query_warehouse(sql)
    assert out["ok"] is False
    assert "blocked" in out["error"]


def test_row_cap_triggers(tiny_warehouse):
    out = q.query_warehouse("SELECT n FROM silver_team_games ORDER BY n", max_rows=500)
    assert out["ok"] is True
    assert len(out["rows"]) == 500
    assert out["truncated"] is True
    assert out["meta"]["returned"] == 500
    assert out["meta"]["row_cap"] == 500


def test_row_cap_respected_when_small(tiny_warehouse):
    out = q.query_warehouse("SELECT n FROM silver_team_games ORDER BY n", max_rows=10)
    assert out["ok"] is True
    assert len(out["rows"]) == 10
    assert out["truncated"] is True


def test_no_truncation_flag_when_complete(tiny_warehouse):
    out = q.query_warehouse("SELECT n FROM silver_team_games WHERE n < 5")
    assert out["ok"] is True
    assert out["truncated"] is False
    assert len(out["rows"]) == 5


def test_unknown_table_blocked(tiny_warehouse):
    out = q.query_warehouse("SELECT * FROM nope_table")
    assert out["ok"] is False
    assert "unknown table" in out["error"]
    assert "nope_table" in out["error"]


def test_filesystem_access_blocked(tiny_warehouse):
    for sql in [
        "SELECT * FROM read_parquet('/tmp/x.parquet')",
        "SELECT * FROM read_csv('s3://bucket/x.csv')",
        "SELECT * FROM '/tmp/x.csv'",
        "SELECT * FROM parquet_scan('/tmp/x.parquet')",
    ]:
        out = q.query_warehouse(sql)
        assert out["ok"] is False, sql
        assert "blocked" in out["error"], (sql, out["error"])


def test_literals_and_comments_not_flagged(tiny_warehouse):
    # Blocked words inside string literals or comments are not code.
    out = q.query_warehouse("SELECT 'copy this drop table' AS note")
    assert out["ok"] is True, out.get("error")
    assert out["rows"] == [{"note": "copy this drop table"}]
    out = q.query_warehouse(
        "-- a comment mentioning delete and drop\n"
        "SELECT TeamCity FROM silver_standings"
    )
    assert out["ok"] is True, out.get("error")
    out = q.query_warehouse(
        "/* pragma attach copy */ SELECT COUNT(*) AS n FROM silver_standings"
    )
    assert out["ok"] is True, out.get("error")


def test_syntax_error_is_honest(tiny_warehouse):
    out = q.query_warehouse("SELECT FROM WHERE")
    assert out["ok"] is False
    assert out["error"].startswith("syntax error"), out["error"]


def test_missing_column_error_is_honest(tiny_warehouse):
    out = q.query_warehouse("SELECT nope_col FROM silver_standings")
    assert out["ok"] is False
    assert "syntax error" in out["error"]


def test_empty_sql_rejected(tiny_warehouse):
    assert q.query_warehouse("")["ok"] is False
    assert q.query_warehouse("   ")["ok"] is False


def test_timeout_is_honest(tiny_warehouse, monkeypatch):
    def _hang(con, sql, timeout_s, max_rows):
        raise TimeoutError(f"query exceeded {timeout_s:g}s")

    monkeypatch.setattr(q, "_run_with_timeout", _hang)
    out = q.query_warehouse("SELECT * FROM silver_team_games", timeout_s=30)
    assert out["ok"] is False
    assert "timed out after 30s" in out["error"]


def test_run_with_timeout_aborts_hung_query():
    class _HangingCon:
        description = (("a",),)

        def execute(self, sql):
            threading.Event().wait(30)

        def close(self):
            pass

    with pytest.raises(TimeoutError):
        q._run_with_timeout(_HangingCon(), "SELECT 1", 0.05, 500)


def test_run_with_timeout_returns_rows():
    con = duckdb.connect(":memory:")
    try:
        cols, rows, truncated = q._run_with_timeout(
            con, "SELECT 1 AS a UNION ALL SELECT 2", 5, 500)
        assert cols == ["a"]
        assert rows == [(1,), (2,)]
        assert truncated is False
    finally:
        con.close()


def test_tool_wrapper(tiny_warehouse):
    from shared.tools.query import query_warehouse_tool

    assert query_warehouse_tool.name == "query_warehouse"
    out = query_warehouse_tool.invoke(
        {"sql": "SELECT TeamCity FROM silver_standings "
                "WHERE WINS = 68"})
    assert out["ok"] is True
    assert out["rows"] == [{"TeamCity": "Oklahoma City"}]
    bad = query_warehouse_tool.invoke({"sql": "DROP TABLE silver_standings"})
    assert bad["ok"] is False
    assert "blocked" in bad["error"]


def test_tool_registered():
    from shared.tools._core import tool_label

    assert tool_label("query_warehouse", desk=True) == "Warehouse query"


def test_read_csv_auto_bypass_closed(tiny_warehouse):
    # Instinct's find: read_csv_auto slipped the old regex guardrail
    # (the blocklist named read_csv but not read_csv_auto, and the
    # FROM-word pattern missed quoted/parenthesised spellings).
    # AST validation must reject every filesystem/network function,
    # however it is spelled or positioned.
    for sql in [
        "SELECT * FROM read_csv_auto('/tmp/x.csv')",
        "SELECT * FROM (read_csv_auto('/tmp/x.csv'))",
        "SELECT * FROM (read_csv_auto('/tmp/x.csv')) AS t(a, b)",
        "SELECT * FROM \"read_csv_auto\"('/tmp/x.csv')",
        "SELECT * FROM read_csv('/tmp/x.csv', auto_detect=true)",
        "SELECT * FROM read_parquet('/tmp/x.parquet')",
        "SELECT * FROM read_json_auto('/tmp/x.json')",
        "SELECT * FROM read_ndjson('/tmp/x.ndjson')",
        "SELECT * FROM parquet_scan('/tmp/x.parquet')",
        "SELECT * FROM (SELECT * FROM read_csv_auto('/tmp/x.csv'))",
        "WITH c AS (SELECT 1 AS n) "
        "SELECT * FROM read_csv_auto('/tmp/x.csv'), c",
        "SELECT * FROM '/tmp/x.csv'",
        "SELECT * FROM 's3://bucket/x.csv'",
        "SELECT * FROM range(3)",
        "SELECT read_blob('/tmp/x.csv')",
        "SELECT read_text('/tmp/x.csv')",
        "SELECT current_setting('memory_limit')",
        "SELECT * INTO sneak FROM silver_standings",
    ]:
        out = q.query_warehouse(sql)
        assert out["ok"] is False, sql
        assert "blocked" in out["error"], (sql, out["error"])


def test_legit_window_and_cte_still_pass(tiny_warehouse):
    out = q.query_warehouse(
        "WITH ranked AS (SELECT TeamCity, WINS, "
        "ROW_NUMBER() OVER (ORDER BY WINS DESC) AS rn "
        "FROM silver_standings) "
        "SELECT TeamCity, WINS FROM ranked WHERE rn <= 2 ORDER BY rn"
    )
    assert out["ok"] is True, out.get("error")
    assert [r["TeamCity"] for r in out["rows"]] == [
        "Oklahoma City", "Boston"]
    out = q.query_warehouse(
        "SELECT CAST(WINS AS DOUBLE) / (WINS + LOSSES) AS pct, "
        "UPPER(TeamCity) AS city FROM silver_standings "
        "WHERE WINS BETWEEN 60 AND 70 ORDER BY pct DESC"
    )
    assert out["ok"] is True, out.get("error")
    assert out["rows"][0]["city"] == "OKLAHOMA CITY"


def test_union_of_selects_passes(tiny_warehouse):
    out = q.query_warehouse(
        "SELECT TeamCity FROM silver_standings WHERE WINS > 65 "
        "UNION ALL SELECT TeamCity FROM silver_standings WHERE WINS < 65"
    )
    assert out["ok"] is True, out.get("error")
    assert {r["TeamCity"] for r in out["rows"]} == {
        "Oklahoma City", "Boston"}


def test_from_position_function_calls_blocked(tiny_warehouse):
    # Independent verification find: sqlglot models FROM unnest(...)
    # as From(this=Unnest) — a Func, not a Table — so the table loop
    # never saw it, and the function allowlist (which named unnest)
    # let it through. A function call in table position is a table
    # source, so it is now rejected structurally, whatever the name.
    for sql in [
        "SELECT * FROM unnest([1, 2, 3])",
        "SELECT * FROM unnest([1, 2, 3]) u(x)",
        "SELECT * FROM silver_standings CROSS JOIN unnest([1])",
        "SELECT * FROM unnest((SELECT WINS FROM silver_standings))",
    ]:
        out = q.query_warehouse(sql)
        assert out["ok"] is False, sql
        assert "table functions" in out["error"], (sql, out["error"])
    # Scalar unnest was never allowlisted (sqlglot names it EXPLODE);
    # it stays blocked as an unknown function.
    out = q.query_warehouse("SELECT unnest([1, 2, 3])")
    assert out["ok"] is False
    assert "blocked" in out["error"], out["error"]
    # Legit table-position shapes still pass: derived tables, VALUES,
    # TABLESAMPLE, and LATERAL over a subquery.
    out = q.query_warehouse("SELECT * FROM (VALUES (1), (2)) t(a)")
    assert out["ok"] is True, out.get("error")
    out = q.query_warehouse(
        "SELECT * FROM silver_standings TABLESAMPLE RESERVOIR(2 ROWS)")
    assert out["ok"] is True, out.get("error")
    out = q.query_warehouse(
        "SELECT * FROM silver_standings, "
        "LATERAL (SELECT WINS FROM silver_standings) t")
    assert out["ok"] is True, out.get("error")
