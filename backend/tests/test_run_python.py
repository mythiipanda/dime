import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
import pytest

from shared import store
from shared.tools.shared import run_python

def test_run_python_math_and_print():
    res = run_python.invoke({"code": "print(1 + 1)\nout = 42"})
    assert res["ok"] is True
    assert res["tool"] == "run_python"
    assert "2" in res["rows"]["printed"]
    assert res["rows"]["out"] == "42"

def test_run_python_polars_structured_rows():
    code = """
import duckdb # should fail if import
"""
    res_banned = run_python.invoke({"code": code})
    assert res_banned["ok"] is False
    assert "unavailable" in res_banned["error"].lower()

def test_run_python_polars_dataframe_out():
    code = """
df = pl.DataFrame({"player": ["Luka", "SGA"], "pts": [33.9, 31.4]})
out = df
"""
    res = run_python.invoke({"code": code})
    assert res["ok"] is True
    assert isinstance(res["rows"], list)
    assert len(res["rows"]) == 2
    assert res["rows"][0]["player"] == "Luka"
    assert res["rows"][0]["pts"] == 33.9

def test_run_python_banned_writes():
    for banned in ["DROP TABLE test", "INSERT INTO silver_boxscores VALUES (1)", "DELETE FROM silver_boxscores"]:
        res = run_python.invoke({"code": banned})
        assert res["ok"] is False
        assert "writes banned" in res["error"].lower()

def test_run_python_duckdb_con(tmp_path, monkeypatch):
    db_file = tmp_path / "test_wh.duckdb"
    con = duckdb.connect(str(db_file))
    con.execute("CREATE TABLE silver_test (name VARCHAR, score DOUBLE)")
    con.execute("INSERT INTO silver_test VALUES ('Jokic', 99.5)")
    con.close()

    monkeypatch.setattr(store, "DB_PATH", db_file)
    code = """
rows = con.execute("SELECT name, score FROM silver_test").fetchall()
print(f"found {len(rows)} row")
out = [{"player": r[0], "rating": r[1]} for r in rows]
"""
    res = run_python.invoke({"code": code})
    assert res["ok"] is True
    assert isinstance(res["rows"], list)
    assert len(res["rows"]) == 1
    assert res["rows"][0]["player"] == "Jokic"
    assert res["rows"][0]["rating"] == 99.5
