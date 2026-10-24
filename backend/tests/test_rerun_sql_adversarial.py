import asyncio
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.tools.league import _validate_readonly_sql, rerun_sql


@pytest.fixture()
def warehouse(monkeypatch, tmp_path):
    wh = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(wh))
    try:
        con.execute(
            "CREATE TABLE silver_standings "
            "(TEAM TEXT, WINS INTEGER, _season TEXT)")
        con.execute(
            "INSERT INTO silver_standings VALUES ('OKC', 68, '2025-26')")
    finally:
        con.close()
    monkeypatch.setattr(store, "connect",
                        lambda **_kw: duckdb.connect(str(wh)))
    return wh


def _count():
    con = store.connect()
    try:
        return con.execute(
            "SELECT COUNT(*) FROM silver_standings").fetchone()[0]
    finally:
        con.close()


WRITES = [
    "INSERT INTO silver_standings VALUES ('X', 1, '2025-26')",
    "insert into silver_standings values ('X', 1, '2025-26')",
    "UPDATE silver_standings SET WINS = 99",
    "DELETE FROM silver_standings",
    "DROP TABLE silver_standings",
    "drop table silver_standings",
    "CREATE TABLE evil AS SELECT * FROM silver_standings",
    "ALTER TABLE silver_standings ADD COLUMN x INT",
    "TRUNCATE silver_standings",
    "REPLACE INTO silver_standings VALUES ('X', 1, '2025-26')",
    "COPY silver_standings TO '/tmp/evil.csv'",
    "VACUUM silver_standings",
    "ATTACH '/tmp/e.db' AS e",
    "PRAGMA memory_limit='1GB'",
    "GRANT SELECT ON silver_standings TO x",
    "INSTALL httpfs",
]

STACKED = [
    "SELECT WINS FROM silver_standings; DROP TABLE silver_standings",
    "SELECT 1; SELECT 2",
    "WITH x AS (SELECT 1) DELETE FROM silver_standings",
    "WITH x AS (SELECT 1) INSERT INTO silver_standings VALUES ('X',1,'s')",
    "SELECT * FROM silver_standings WHERE TEAM='x'; --",
    "SELECT 'a;b' FROM silver_standings",
]

DISALLOWED_TABLES = [
    "SELECT * FROM main.silver_standings",
    "SELECT * FROM information_schema.tables",
    "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT * FROM pragma_table_info('silver_standings')",
    "SELECT read_csv('/etc/passwd')",
]

NON_SELECT = [
    "-- hi\nSELECT WINS FROM silver_standings",
    "/*x*/SELECT WINS FROM silver_standings",
    "SEL/**/ECT WINS FROM silver_standings",
    "\u200bSELECT WINS FROM silver_standings",
    "",
    "   ",
]

LEGIT = [
    "SELECT WINS FROM silver_standings",
    "SeLeCt WINS FrOm silver_standings",
    "SELECT WINS FROM silver_standings WHERE TEAM='Oct''s team'",
    "SELECT WINS FROM silver_standings LIMIT 1 OFFSET 0",
    "SELECT * FROM (SELECT WINS FROM silver_standings)",
    "WITH a AS (SELECT 1) SELECT * FROM silver_standings",
    "WITH foo AS (SELECT WINS FROM silver_standings) SELECT * FROM foo",
    "SELECT WINS FROM silver_standings;;",
]


def test_rerun_sql_accepts_captured_cte_with_known_physical_source(monkeypatch):
    import shared.tools.league as league

    sql = (
        "WITH celtics_games AS (SELECT game_id, "
        "MAX(CASE WHEN wl = 'W' THEN 1 ELSE 0 END) AS is_win, "
        "SUM(pts) AS game_points FROM silver_hist_gamelogs "
        "WHERE _season = '2024-25' AND team_abbreviation = 'BOS' "
        "GROUP BY game_id) SELECT COUNT(*) AS GAMES, "
        "SUM(is_win) AS WINS, SUM(1 - is_win) AS LOSSES, "
        "SUM(game_points) AS TOTAL_POINTS FROM celtics_games"
    )

    class FakeConnection:
        def execute(self, statement):
            assert statement == "SHOW TABLES"
            return self

        def fetchall(self):
            return [("silver_hist_gamelogs",)]

        def close(self):
            pass

    executed = []

    def fake_executor(connection, query, timeout_seconds):
        executed.append(query)
        return ["GAMES"], [(0,)]

    monkeypatch.setattr(league.store, "connect", lambda **_kwargs: FakeConnection())
    monkeypatch.setattr(league, "_execute_with_timeout", fake_executor)

    result = asyncio.run(league.rerun_sql(sql))

    assert result["ok"] is True
    assert result["sql"] == sql
    assert result["rows"] == [{"GAMES": 0}]
    assert executed == [sql]


def test_rerun_sql_rejects_unknown_physical_table_before_execution(monkeypatch):
    import shared.tools.league as league

    class FakeConnection:
        def execute(self, statement):
            assert statement == "SHOW TABLES"
            return self

        def fetchall(self):
            return [("silver_hist_gamelogs",)]

        def close(self):
            pass

    executed = []
    monkeypatch.setattr(league.store, "connect", lambda **_kwargs: FakeConnection())
    monkeypatch.setattr(
        league, "_execute_with_timeout",
        lambda *args: executed.append(args[1]),
    )

    result = asyncio.run(
        league.rerun_sql("SELECT COUNT(*) FROM not_a_declared_table")
    )

    assert result["ok"] is False
    assert result["error"] == "unknown or unavailable tables"
    assert executed == []


@pytest.mark.parametrize("bad", WRITES + STACKED + DISALLOWED_TABLES + NON_SELECT)
def test_validate_rejects_adversarial_sql(bad):
    with pytest.raises(ValueError):
        _validate_readonly_sql(bad, {"silver_standings"})


@pytest.mark.parametrize("good", LEGIT)
def test_validate_accepts_legit_reads(good):
    assert _validate_readonly_sql(good, {"silver_standings"})


@pytest.mark.parametrize("bad", WRITES + STACKED + DISALLOWED_TABLES)
def test_rerun_sql_rejects_without_mutation(warehouse, bad):
    out = asyncio.run(rerun_sql(bad))
    assert out["ok"] is False
    assert out["error"]
    assert _count() == 1


def test_rerun_sql_legit_read_returns_rows(warehouse):
    out = asyncio.run(rerun_sql("SELECT TEAM, WINS FROM silver_standings"))
    assert out["ok"] is True
    assert out["rows"] == [{"TEAM": "OKC", "WINS": 68}]
