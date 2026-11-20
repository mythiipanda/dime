import asyncio
import duckdb
import pytest
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


@pytest.mark.parametrize("bad", [
    "DROP TABLE silver_standings",
    "INSERT INTO silver_standings VALUES ('X', 1, '2025-26')",
    "UPDATE silver_standings SET WINS = 99",
    "DELETE FROM silver_standings",
    "SELECT WINS FROM silver_standings; DROP TABLE silver_standings",
    "SELECT WINS FROM silver_standings; SELECT WINS FROM silver_standings",
])
def test_validate_rejects_write_sql(bad):
    with pytest.raises(ValueError):
        _validate_readonly_sql(bad, {"silver_standings"})


@pytest.mark.parametrize("bad", [
    "DROP TABLE silver_standings",
    "INSERT INTO silver_standings VALUES ('X', 1, '2025-26')",
    "SELECT WINS FROM silver_standings; DROP TABLE silver_standings",
])
def test_rerun_sql_rejects_write_sql(warehouse, bad):
    out = asyncio.run(rerun_sql(bad))
    assert out["ok"] is False
    assert out["error"]
    con = store.connect()
    try:
        n = con.execute("SELECT COUNT(*) FROM silver_standings").fetchone()[0]
    finally:
        con.close()
    assert n == 1
