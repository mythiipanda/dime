import asyncio
import importlib
import importlib.util
import duckdb
import pytest
from shared import store
from shared.tools import shared as shared_mod

sql_exec_mod = importlib.import_module("shared.tools.sql_exec")


def _scipy_stats_sklearn_available() -> bool:
    try:
        import scipy.stats
        from sklearn.linear_model import Ridge
        return bool(scipy.stats and Ridge)
    except Exception:
        return False


@pytest.fixture()
def warehouse(monkeypatch, tmp_path):
    wh = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(wh))
    try:
        con.execute("CREATE TABLE silver_standings (TEAM TEXT, WINS INTEGER, _season TEXT)")
        con.execute("INSERT INTO silver_standings VALUES ('OKC', 68, '2025-26'), ('CLE', 64, '2025-26'), ('BOS', 61, '2025-26')")
    finally:
        con.close()
    monkeypatch.setenv("DIME_WAREHOUSE", str(wh))
    monkeypatch.setattr(store, "WAREHOUSE", wh, raising=False)
    monkeypatch.setattr(store, "DB_PATH", wh, raising=False)
    monkeypatch.setattr(store, "connect", lambda **_kw: duckdb.connect(str(wh)))
    return wh


def test_run_python_scientific_libraries_and_duckdb(warehouse, tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("DIME_THREAD_WORKSPACE", str(ws))
    code = """
import numpy as np
import scipy.linalg
import polars as pl
import matplotlib.pyplot as plt

rows = con.execute("SELECT ROW_NUMBER() OVER (ORDER BY WINS DESC) AS idx, TEAM, WINS FROM silver_standings").fetchall()
df = pl.DataFrame(rows, schema=["idx", "TEAM", "WINS"], orient="row")
X = np.column_stack([df["idx"].to_numpy(), np.ones(df.height)])
y = df["WINS"].to_numpy().astype(float)
lam = 1.0
coef = scipy.linalg.solve(X.T @ X + lam * np.eye(2), X.T @ y)
fig, ax = plt.subplots()
ax.bar(df["TEAM"].to_list(), df["WINS"].to_list())
fig.savefig("standings.png")
plt.close(fig)
print("SCIENTIFIC_OK")
out = {"slope": float(coef[0]), "rows": int(df.height)}
"""
    res = shared_mod.run_python.invoke({"code": code})
    assert res["ok"] is True
    assert "SCIENTIFIC_OK" in res["stdout"]
    assert res["rows"]["out"]["rows"] == 3
    assert isinstance(res["rows"]["out"]["slope"], float)
    assert "standings.png" in res["workspace_files"]


@pytest.mark.skipif(not _scipy_stats_sklearn_available(), reason="host Python scipy.stats/sklearn wheel unavailable")
def test_run_python_scipy_stats_and_sklearn_ridge(warehouse, tmp_path, monkeypatch):
    ws = tmp_path / "ws_sk"
    ws.mkdir()
    monkeypatch.setenv("DIME_THREAD_WORKSPACE", str(ws))
    code = """
import numpy as np
import scipy.stats
from sklearn.linear_model import Ridge

rows = con.execute("SELECT ROW_NUMBER() OVER (ORDER BY WINS DESC) AS idx, WINS FROM silver_standings").fetchall()
idx = np.array([r[0] for r in rows], dtype=float)
y = np.array([r[1] for r in rows], dtype=float)
reg = Ridge(alpha=1.0).fit(idx.reshape(-1, 1), y)
corr = scipy.stats.pearsonr(idx, y).statistic
out = {"coef": float(reg.coef_[0]), "corr": float(corr), "rows": len(rows)}
"""
    res = shared_mod.run_python.invoke({"code": code})
    assert res["ok"] is True
    assert res["rows"]["out"]["rows"] == 3
    assert isinstance(res["rows"]["out"]["coef"], float)


def test_run_python_persists_thread_workspace_files_across_calls(warehouse, tmp_path, monkeypatch):
    ws = tmp_path / "thread_ws"
    ws.mkdir()
    monkeypatch.setenv("DIME_THREAD_WORKSPACE", str(ws))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-secret-must-not-leak")

    res1 = shared_mod.run_python.invoke({"code": """
from pathlib import Path
import os
import polars as pl
assert "OPENROUTER_API_KEY" not in os.environ
pl.DataFrame({"team": ["OKC", "CLE"], "wins": [68, 64]}).write_parquet("cached.parquet")
out = {"saved": True, "ws": str(Path.cwd())}
"""})
    assert res1["ok"] is True
    assert "cached.parquet" in res1["workspace_files"]

    res2 = shared_mod.run_python.invoke({"code": """
import polars as pl
df = pl.read_parquet("cached.parquet")
out = {"count": int(df.height), "max_wins": int(df["wins"].max())}
"""})
    assert res2["ok"] is True
    assert res2["rows"]["out"] == {"count": 2, "max_wins": 68}


def test_run_python_readonly_duckdb_and_recovery_hint(warehouse, tmp_path, monkeypatch):
    ws = tmp_path / "ro_ws"
    ws.mkdir()
    monkeypatch.setenv("DIME_THREAD_WORKSPACE", str(ws))
    res_write = shared_mod.run_python.invoke({"code": """
con.execute("CREATE TABLE bad_table (x INT)")
"""})
    assert res_write["ok"] is False

    res_missing = shared_mod.run_python.invoke({"code": """
out = con.execute("SELECT * FROM missing_table_xyz").fetchall()
"""})
    assert res_missing["ok"] is False
    assert "Valid tables:" in res_missing["recovery_hint"]
    assert "silver_standings" in res_missing["recovery_hint"]


def test_sql_exec_zero_rows_and_long_sql_and_recovery_hint(warehouse, monkeypatch):
    padding = " " * 9000
    long_sql = f"SELECT TEAM, WINS FROM silver_standings WHERE WINS = 999999{padding}"
    assert len(long_sql) > 8000

    res_empty = asyncio.run(sql_exec_mod.sql_exec.ainvoke({"sql": long_sql}))
    assert res_empty["ok"] is True
    assert res_empty["rows"] == []
    assert res_empty["row_count"] == 0
    assert res_empty["meta"]["empty_observation"] is True

    monkeypatch.setenv("DIME_STRICT_NONEMPTY_SQL", "1")
    res_strict = asyncio.run(sql_exec_mod.sql_exec.ainvoke({"sql": "SELECT TEAM FROM silver_standings WHERE WINS = 999999"}))
    assert res_strict["ok"] is False

    monkeypatch.delenv("DIME_STRICT_NONEMPTY_SQL", raising=False)
    res_err = asyncio.run(sql_exec_mod.sql_exec.ainvoke({"sql": "SELECT nonexistent_col FROM silver_standings"}))
    assert res_err["ok"] is False
    assert "recovery_hint" in res_err
    assert "warehouse_schema" in res_err["recovery_hint"]

    res_typo = asyncio.run(sql_exec_mod.sql_exec.ainvoke({"sql": "SELECT WINSX FROM silver_standings"}))
    assert res_typo["ok"] is False
    assert "silver_standings.WINS" in res_typo["recovery_hint"]


def test_sql_exec_refusal_hints_steer_to_warehouse_schema(warehouse):
    res_describe = asyncio.run(sql_exec_mod.sql_exec.ainvoke({"sql": "DESCRIBE silver_standings"}))
    assert res_describe["ok"] is False
    assert "SELECT or WITH" in res_describe["recovery_hint"]
    assert "warehouse_schema" in res_describe["recovery_hint"]

    res_show = asyncio.run(sql_exec_mod.sql_exec.ainvoke({"sql": "SHOW TABLES"}))
    assert res_show["ok"] is False
    assert "warehouse_schema" in res_show["recovery_hint"]

    res_info = asyncio.run(sql_exec_mod.sql_exec.ainvoke(
        {"sql": "SELECT table_name FROM information_schema.tables"}))
    assert res_info["ok"] is False
    assert "information_schema" in res_info["recovery_hint"]
    assert "warehouse_schema" in res_info["recovery_hint"]

    res_catalog_fn = asyncio.run(sql_exec_mod.sql_exec.ainvoke(
        {"sql": "SELECT * FROM warehouse_schema()"}))
    assert res_catalog_fn["ok"] is False
    assert "warehouse_schema" in res_catalog_fn["recovery_hint"]

    res_guess = asyncio.run(sql_exec_mod.sql_exec.ainvoke(
        {"sql": "SELECT * FROM silver_bbref_gamelogs_2024_25"}))
    assert res_guess["ok"] is False
    assert "declared silver" in res_guess["recovery_hint"]
    assert "warehouse_schema" in res_guess["recovery_hint"]
||||||| 002e08dd


def test_sql_exec_binder_hint_names_column_and_candidates(warehouse):
    res = asyncio.run(sql_exec_mod.sql_exec.ainvoke(
        {"sql": "SELECT team_abbreviation FROM silver_standings"}))
    assert res["ok"] is False
    hint = res["recovery_hint"]
    assert "'team_abbreviation'" in hint
    assert "silver_standings" in hint

    res_func = asyncio.run(sql_exec_mod.sql_exec.ainvoke(
        {"sql": "SELECT sum(TEAM) FROM silver_standings"}))
    assert res_func["ok"] is False
    assert "CAST" in res_func["recovery_hint"]