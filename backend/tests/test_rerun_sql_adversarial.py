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
    "WITH foo AS (SELECT WINS FROM silver_standings) SELECT * FROM foo",
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
    "SELECT WINS FROM silver_standings;;",
]


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
