"""One-click SQL re-run (ROADMAP Phase 1 #1, second half).

rerun_sql re-executes the exact SQL shown behind a text_to_sql answer.
Hermetic: no network, no LLM, no real warehouse.
"""

import asyncio
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store
from app.routes import SqlRerunBody, api_sql_rerun
from app.tools import league
from app.tools.league import (
    RERUN_ROW_CAP,
    RERUN_TIMEOUT_S,
    _execute_with_timeout,
    _validate_readonly_sql,
    rerun_sql,
)

SQL = ("SELECT WINS, LOSSES FROM silver_standings "
       "WHERE TEAM = 'OKC' AND _season = '2025-26'")


@pytest.fixture()
def warehouse(monkeypatch, tmp_path):
    wh = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(wh))
    try:
        con.execute(
            "CREATE TABLE silver_standings "
            "(TEAM TEXT, WINS INTEGER, LOSSES INTEGER, _season TEXT)")
        con.execute(
            "INSERT INTO silver_standings VALUES ('OKC', 68, 14, '2025-26')")
        for i in range(29):
            con.execute(
                "INSERT INTO silver_standings VALUES "
                f"('T{i:02d}', {i}, {82 - i}, '2025-26')")
    finally:
        con.close()
    monkeypatch.setattr(store, "connect",
                        lambda **_kw: duckdb.connect(str(wh)))
    return wh


def test_validate_accepts_select_and_with():
    present = {"silver_standings"}
    assert _validate_readonly_sql(SQL, present) == SQL
    assert _validate_readonly_sql(
        "WITH t AS (SELECT 1 AS x) SELECT x FROM silver_standings", present)
    assert _validate_readonly_sql(SQL + ";", present) == SQL


@pytest.mark.parametrize("bad", [
    "INSERT INTO silver_standings VALUES ('X', 1, 2, '2025-26')",
    "UPDATE silver_standings SET WINS = 99",
    "DELETE FROM silver_standings",
    "DROP TABLE silver_standings",
    "ALTER TABLE silver_standings ADD COLUMN x INT",
    "CREATE TABLE evil AS SELECT 1",
    "SELECT * FROM silver_standings; DROP TABLE silver_standings",
    "SELECT WINS FROM silver_standings WHERE TEAM = 'OKC'; SELECT 1",
    "PRAGMA table_info(silver_standings)",
    "SELECT * FROM silver_unknown",
    "SELECT * FROM fetch_log",
    "",
    "hello world",
])
def test_validate_rejects_writes_and_unknown_tables(bad):
    with pytest.raises(ValueError):
        _validate_readonly_sql(bad, {"silver_standings"})


def test_rerun_returns_rows_columns_and_ms(warehouse):
    out = asyncio.run(rerun_sql(SQL))
    assert out["ok"] is True
    assert out["columns"] == ["WINS", "LOSSES"]
    assert out["rows"][0] == {"WINS": 68, "LOSSES": 14}
    assert out["sql"] == SQL
    assert out["capped"] is False
    assert isinstance(out["ms"], int) and out["ms"] >= 0


def test_rerun_enforces_row_cap(warehouse):
    out = asyncio.run(rerun_sql(
        "SELECT TEAM, WINS FROM silver_standings WHERE _season = '2025-26'"))
    assert out["ok"] is True
    assert len(out["rows"]) == RERUN_ROW_CAP
    assert RERUN_ROW_CAP == 25
    assert out["capped"] is True


def test_rerun_rejects_write_sql(warehouse):
    out = asyncio.run(rerun_sql("DELETE FROM silver_standings"))
    assert out["ok"] is False
    assert "write" in out["error"] or "SELECT" in out["error"]
    con = store.connect()
    try:
        n = con.execute("SELECT COUNT(*) FROM silver_standings").fetchone()[0]
    finally:
        con.close()
    assert n == 30


def test_rerun_rejects_stacked_statements(warehouse):
    out = asyncio.run(
        rerun_sql("SELECT * FROM silver_standings; DROP TABLE silver_standings"))
    assert out["ok"] is False
    assert "stacked" in out["error"]


def test_rerun_maps_timeout_to_error(warehouse, monkeypatch):
    def _boom(_con, _sql, _timeout):
        raise TimeoutError(f"query exceeded {RERUN_TIMEOUT_S:g}s")

    monkeypatch.setattr(league, "_execute_with_timeout", _boom)
    out = asyncio.run(rerun_sql(SQL))
    assert out["ok"] is False
    assert "exceeded" in out["error"]
    assert out["sql"] == SQL


def test_rerun_reports_bad_sql_error(warehouse):
    bad = "SELECT nope FROM silver_standings"
    out = asyncio.run(rerun_sql(bad))
    assert out["ok"] is False
    assert out["error"]
    assert out["sql"] == bad


def test_route_clamps_and_returns_rows(warehouse):
    out = asyncio.run(api_sql_rerun(SqlRerunBody(sql=SQL)))
    assert out["ok"] is True
    assert out["rows"]["rows"][0] == {"WINS": 68, "LOSSES": 14}
    assert out["rows"]["columns"] == ["WINS", "LOSSES"]
    assert isinstance(out["rows"]["ms"], int)


def test_route_rejects_empty_and_long_sql(warehouse):
    assert asyncio.run(api_sql_rerun(SqlRerunBody(sql="")))["ok"] is False
    assert asyncio.run(
        api_sql_rerun(SqlRerunBody(sql="SELECT 1 " * 5000)))["ok"] is False


def test_route_surfaces_validation_error(warehouse):
    out = asyncio.run(
        api_sql_rerun(SqlRerunBody(sql="DROP TABLE silver_standings")))
    assert out["ok"] is False
    assert out["error"]
