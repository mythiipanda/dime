import asyncio
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.tools import league
from shared.tools.sql_exec import sql_exec


class _Connection:
    def __init__(self, real, counter):
        self._real = real
        self._counter = counter

    @property
    def description(self):
        return self._real.description

    def execute(self, statement, *args, **kwargs):
        text = str(statement).lstrip().upper()
        if text.startswith("SELECT") or text.startswith("WITH"):
            self._counter["user_selects"] += 1
        return self._real.execute(statement, *args, **kwargs)

    def close(self):
        pass


@pytest.fixture()
def warehouse(monkeypatch):
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            "CREATE TABLE silver_standings "
            "(TEAM TEXT, WINS INTEGER, _season TEXT)")
        con.execute(
            "INSERT INTO silver_standings VALUES ('OKC', 68, '2025-26')")
        for i in range(29):
            con.execute(
                "INSERT INTO silver_standings VALUES (?, ?, '2025-26')",
                [f"T{i}", i])
        con.execute(
            "CREATE TABLE silver_playoffs "
            "(TEAM TEXT, WINS INTEGER, _season TEXT)")
        con.execute(
            "INSERT INTO silver_playoffs VALUES ('OKC', 10, '2025-26')")
    except Exception:
        con.close()
        raise
    counter = {"user_selects": 0}
    league._clear_warehouse_schema_cache()
    monkeypatch.setattr(store, "connect",
                        lambda **_kw: _Connection(con, counter))
    yield counter
    league._clear_warehouse_schema_cache()
    con.close()


def _run(sql):
    return asyncio.run(sql_exec.ainvoke({"sql": sql}))


@pytest.mark.parametrize("sql,expected", [
    ("SELECT TEAM, WINS FROM silver_standings", ["silver_standings"]),
    ("WITH cte AS (SELECT * FROM silver_standings) SELECT * FROM cte",
     ["silver_standings"]),
    ("WITH silver_playoffs AS (SELECT * FROM silver_standings) "
     "SELECT * FROM silver_playoffs", ["silver_standings"]),
    ("WITH outer_cte AS (SELECT * FROM "
     "(SELECT * FROM silver_standings) AS inner_sub) "
     "SELECT * FROM outer_cte", ["silver_standings"]),
    ("SELECT s.TEAM, s.WINS, p.WINS AS PWINS "
     "FROM silver_standings s, silver_playoffs p "
     "WHERE s.TEAM = p.TEAM",
     ["silver_playoffs", "silver_standings"]),
    ("SELECT s.TEAM, s.WINS, p.WINS AS PWINS "
     "FROM silver_standings s JOIN silver_playoffs p "
     "ON s.TEAM = p.TEAM",
     ["silver_playoffs", "silver_standings"]),
    ('SELECT TEAM, WINS FROM "silver_standings" AS s',
     ["silver_standings"]),
    ("SELECT TEAM, WINS FROM (SELECT TEAM, WINS FROM silver_standings) AS sub",
     ["silver_standings"]),
])
def test_sql_exec_tables_are_validated_physical_sources(
        warehouse, sql, expected):
    result = _run(sql)
    assert result["ok"] is True
    assert warehouse["user_selects"] == 1
    assert result["meta"]["tables"] == expected
    assert result["season_semantics"]["tables"] == expected
    assert result["meta"]["coverage"].startswith(
        f"Agent-written SQL over {', '.join(expected)}; ")


def test_sql_exec_season_attribution_uses_validated_table(warehouse):
    result = _run(
        "SELECT s._season, s.TEAM FROM silver_standings AS s")
    assert result["ok"] is True
    assert warehouse["user_selects"] == 1
    assert result["meta"]["tables"] == ["silver_standings"]
    columns = result["season_semantics"]["season_columns"]
    assert any(
        entry.get("table") == "silver_standings"
        and entry.get("column") == "_season"
        and entry.get("attribution_supported") is True
        for entry in columns)
    assert result["season_semantics"]["resolved_labels"]


def test_sql_exec_refusals_and_cap_still_apply(warehouse):
    refused = _run("SELECT * FROM not_a_declared_table")
    assert refused["ok"] is False
    assert "unknown" in refused["error"]
    assert warehouse["user_selects"] == 0
    stacked = _run(
        "SELECT TEAM FROM silver_standings; "
        "SELECT TEAM FROM silver_playoffs")
    assert stacked["ok"] is False
    assert warehouse["user_selects"] == 0
    capped = _run("SELECT WINS FROM silver_standings ORDER BY WINS")
    assert capped["ok"] is True
    assert capped["meta"]["tables"] == ["silver_standings"]
    assert capped["meta"]["capped"] is True
    assert len(capped["rows"]) == 25
