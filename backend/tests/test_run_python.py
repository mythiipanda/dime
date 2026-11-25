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
    assert res["rows"]["out"] == 42

def test_run_python_rejects_empty_code():
    res = run_python.invoke({"code": "   "})
    assert res["ok"] is False
    assert res["error"] == "empty code"

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

def test_run_python_syntax_error_marks_failing_line():
    code = "x = 1\ny = (2 +\nout = x + y\n"
    res = run_python.invoke({"code": code})
    assert res["ok"] is False
    assert res["error_type"] == "SyntaxError"
    assert res["error"].startswith("SyntaxError:")
    assert ">>    2| y = (2 +" in res["error"]
    assert res["error_line"] == 2
    assert "   3| out = x + y" in res["code_context"]
    assert "syntax" in res["recovery_hint"].lower()

def test_run_python_runtime_error_marks_failing_line():
    code = "total = 10\nratio = total / denomiator\nout = ratio\n"
    res = run_python.invoke({"code": code})
    assert res["ok"] is False
    assert res["error_type"] == "NameError"
    assert res["error_line"] == 2
    assert ">>    2| ratio = total / denomiator" in res["code_context"]
    assert "code around line 2" in res["error"]

def test_run_python_banned_writes():
    for banned in ["DROP TABLE silver_boxscores", "CREATE TABLE silver_scratch (x INT)", "DELETE FROM silver_boxscores"]:
        res = run_python.invoke({"code": f"con.execute({banned!r})"})
        assert res["ok"] is False
        assert "read-only" in res["error"].lower() or "read only" in res["error"].lower()

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
    assert "warning" not in res

def test_run_python_warns_when_con_rebound(tmp_path, monkeypatch):
    db_file = tmp_path / "test_wh.duckdb"
    con = duckdb.connect(str(db_file))
    con.execute("CREATE TABLE silver_test (name VARCHAR)")
    con.close()

    monkeypatch.setattr(store, "DB_PATH", db_file)
    res = run_python.invoke({"code": "import duckdb\ncon = duckdb.connect()\nout = 1"})
    assert res["ok"] is True
    assert "warning" in res
    assert "rebound" in res["warning"]
    assert "preloaded `con`" in res["warning"]

def test_run_python_newline_in_string_gets_triple_quote_hint():
    code = 'x = 1\nprint("\nFirst 5 rows:")\nout = x\n'
    res = run_python.invoke({"code": code})
    assert res["ok"] is False
    assert res["error_type"] == "SyntaxError"
    assert "unterminated" in res["error"]
    assert "triple" in res["recovery_hint"].lower()
    assert "newline" in res["recovery_hint"].lower()

def test_run_python_plain_syntax_error_keeps_generic_hint():
    code = "x = 1\ny = (2 +\nout = x + y\n"
    res = run_python.invoke({"code": code})
    assert res["ok"] is False
    assert "triple" not in res["recovery_hint"].lower()
