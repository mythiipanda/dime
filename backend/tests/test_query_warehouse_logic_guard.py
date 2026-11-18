
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import query as q
from shared import store

@pytest.fixture()
def tmp_warehouse(tmp_path, monkeypatch):
    db = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(db))
    con.execute(
        "CREATE TABLE silver_standings "
        "(TeamCity VARCHAR, WINS INTEGER, LOSSES INTEGER, _season VARCHAR)"
    )
    con.execute(
        "INSERT INTO silver_standings VALUES "
        "('Oklahoma City', 68, 14, '2025-26'), "
        "('Boston', 61, 21, '2025-26'), "
        "('Denver', 50, 32, '2025-26')"
    )
    con.execute("CREATE TABLE private_notes (x INTEGER)")
    con.close()
    monkeypatch.setattr(store, "DB_PATH", db)
    return db

def test_source_module_is_backend_shared_query():
    expected = (
        Path(__file__).resolve().parent.parent / "shared" / "query.py"
    ).resolve()
    assert Path(q.__file__).resolve() == expected

def test_and_condition(tmp_warehouse):
    out = q.query_warehouse(
        "SELECT TeamCity FROM silver_standings WHERE WINS > 60 AND LOSSES > 15"
    )
    assert out["ok"] is True, out.get("error")
    assert out["rows"] == [{"TeamCity": "Boston"}]

def test_or_condition(tmp_warehouse):
    out = q.query_warehouse(
        "SELECT TeamCity FROM silver_standings "
        "WHERE WINS = 68 OR TeamCity = 'Denver' ORDER BY WINS DESC"
    )
    assert out["ok"] is True, out.get("error")
    assert out["rows"] == [
        {"TeamCity": "Oklahoma City"},
        {"TeamCity": "Denver"},
    ]

def test_not_condition(tmp_warehouse):
    out = q.query_warehouse(
        "SELECT TeamCity FROM silver_standings "
        "WHERE NOT (WINS > 60) ORDER BY WINS DESC"
    )
    assert out["ok"] is True, out.get("error")
    assert out["rows"] == [{"TeamCity": "Denver"}]

def test_nested_condition(tmp_warehouse):
    out = q.query_warehouse(
        "SELECT TeamCity FROM silver_standings "
        "WHERE (WINS > 60 AND LOSSES < 20) OR (WINS < 55 AND LOSSES > 30) "
        "ORDER BY WINS DESC"
    )
    assert out["ok"] is True, out.get("error")
    assert out["rows"] == [
        {"TeamCity": "Oklahoma City"},
        {"TeamCity": "Denver"},
    ]

def test_case_sum_aggregate(tmp_warehouse):
    out = q.query_warehouse(
        "SELECT "
        "SUM(CASE WHEN WINS > 60 THEN 1 ELSE 0 END) AS qualified, "
        "SUM(WINS) AS total_wins FROM silver_standings "
        "WHERE _season='2025-26' AND LOSSES >= 14"
    )
    assert out["ok"] is True, out.get("error")
    assert out["rows"] == [{"qualified": 2, "total_wins": 179}]

def test_no_condition_control(tmp_warehouse):
    out = q.query_warehouse("SELECT COUNT(*) AS n FROM silver_standings")
    assert out["ok"] is True, out.get("error")
    assert out["rows"] == [{"n": 3}]

def test_false_condition_control(tmp_warehouse):
    out = q.query_warehouse(
        "SELECT COUNT(*) AS n FROM silver_standings WHERE 1 = 0"
    )
    assert out["ok"] is True, out.get("error")
    assert out["rows"] == [{"n": 0}]

@pytest.mark.parametrize("sql", [
    "SELECT COUNT(*) FROM silver_standings "
    "WHERE read_csv('/tmp/x.csv') AND WINS > 1",
    "SELECT COUNT(*) FROM silver_standings "
    "WHERE WINS > 1 OR read_csv('/tmp/x.csv')",
    "SELECT COUNT(*) FROM silver_standings "
    "WHERE NOT read_csv('/tmp/x.csv')",
])
def test_prohibited_function_nested_in_logic_blocked(tmp_warehouse, sql):
    out = q.query_warehouse(sql)
    assert out["ok"] is False, sql
    assert "function not allowed: read_csv" in out["error"], out["error"]

@pytest.mark.parametrize("sql", [
    "SELECT * FROM read_parquet('/tmp/x.parquet')",
    "SELECT * FROM read_csv_auto('/tmp/x.csv')",
    "SELECT * FROM parquet_scan('/tmp/x.parquet')",
    "SELECT * FROM '/tmp/x.csv'",
    "SELECT read_blob('/tmp/x.csv')",
])
def test_external_io_blocked(tmp_warehouse, sql):
    out = q.query_warehouse(sql)
    assert out["ok"] is False, sql
    assert "blocked" in out["error"], (sql, out["error"])

@pytest.mark.parametrize("sql", [
    "INSERT INTO silver_standings VALUES ('X', 1, 1, '2025-26')",
    "UPDATE silver_standings SET WINS = 0",
    "DELETE FROM silver_standings",
    "DROP TABLE silver_standings",
    "CREATE TABLE evil (x INTEGER)",
    "COPY silver_standings TO '/tmp/x.csv'",
])
def test_writes_blocked(tmp_warehouse, sql):
    out = q.query_warehouse(sql)
    assert out["ok"] is False, sql
    assert "blocked" in out["error"], (sql, out["error"])
    intact = q.query_warehouse("SELECT COUNT(*) AS n FROM silver_standings")
    assert intact["rows"] == [{"n": 3}]

def test_multiple_statements_blocked(tmp_warehouse):
    out = q.query_warehouse("SELECT 1; SELECT 2")
    assert out["ok"] is False
    assert "multiple statements" in out["error"]

@pytest.mark.parametrize("sql", [
    "SELECT * FROM nope_table",
    "SELECT * FROM private_notes",
    "SELECT * FROM information_schema.tables",
])
def test_unknown_and_private_tables_blocked(tmp_warehouse, sql):
    out = q.query_warehouse(sql)
    assert out["ok"] is False, sql
    assert "blocked" in out["error"], (sql, out["error"])

def test_injection_literal_stays_literal(tmp_warehouse):
    out = q.query_warehouse(
        "SELECT TeamCity FROM silver_standings "
        "WHERE TeamCity = 'x'' OR ''1''=''1'"
    )
    assert out["ok"] is True, out.get("error")
    assert out["rows"] == []
    intact = q.query_warehouse("SELECT COUNT(*) AS n FROM silver_standings")
    assert intact["rows"] == [{"n": 3}]
