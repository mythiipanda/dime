from analyst.tools import core


def test_clean_code_passes():
    assert core._run_python_violations(
        "rows = con.execute('select 1').fetchall()\n"
        "out = len(rows)\n") == []
    assert core._run_python_violations(
        "def f(x):\n    return x * 2\nout = f(3)\n") == []


def test_javascript_markers():
    rules = {v["rule"] for v in core._run_python_violations(
        "const rows = fetchAll('select * from silver_leaders_pts');\n"
        "console.log(rows);\n")}
    assert any("JavaScript" in r for r in rules)
    assert any("fetchAll" in r for r in rules)


def test_duckdb_connect_and_reassign():
    vs = core._run_python_violations(
        "con = duckdb.connect('warehouse.duckdb')\n")
    rules = {v["rule"] for v in vs}
    assert any("duckdb.connect" in r for r in rules)
    assert any("reassign" in r for r in rules)


def test_sqlite_paths_and_dime_analyst():
    vs = core._run_python_violations(
        "import sqlite3\nfrom dime_analyst import tools\n")
    rules = {v["rule"] for v in vs}
    assert any("file paths" in r for r in rules)
    assert any("dime_analyst" in r for r in rules)


def test_top_level_return():
    vs = core._run_python_violations("x = 1\nreturn x\n")
    assert any("top level" in v["rule"] for v in vs)
    assert core._run_python_violations(
        "def f():\n    return 1\nout = f()\n") == []


def test_violations_carry_fix_and_line():
    vs = core._run_python_violations("x = 1\nconsole.log(x)\n")
    assert len(vs) == 1
    assert vs[0]["line"] == 2
    assert "print()" in vs[0]["fix"]
    assert vs[0]["code"]


def test_wrapper_rejects_before_execution():
    wrapped = core.register()["run_python"]
    res = wrapped.invoke({"code": "console.log('hi')\n"})
    assert res["ok"] is False
    assert res["rows"] == []
    assert res["columns"]
    assert res["violations"]
    assert any("print()" in v["fix"] for v in res["violations"])
