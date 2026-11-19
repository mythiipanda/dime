import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from uuid import uuid4

import duckdb
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared import store as warehouse_store
from shared.config import settings
from v2.main import app
from v2.notebooks import runner, sql
from v2.notebooks.store import OUTPUT_CAP

client = TestClient(app)


def test_notebook_put_cors_preflight():
    origin = settings.cors_origins[0]
    response = client.options("/api/notebooks/" + "a" * 32, headers={
        "Origin": origin,
        "Access-Control-Request-Method": "PUT",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == origin
    assert "PUT" in response.headers["access-control-allow-methods"]


@pytest.fixture(autouse=True)
def notebook_environment(tmp_path, monkeypatch):
    directory = tmp_path / "notebooks"
    monkeypatch.setenv("DIME_NOTEBOOK_DIR", str(directory))
    monkeypatch.delenv("DIME_NOTEBOOK_PYTHON", raising=False)
    path = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute("CREATE TABLE silver_player_season AS SELECT i AS player_id, 'Player ' || i AS player, i::DOUBLE / 10 AS ppg FROM range(6000) t(i)")
        con.execute("CREATE TABLE private_notes AS SELECT 'secret' AS value")
    monkeypatch.setattr(warehouse_store, "DB_PATH", path)
    return directory


def create(**extra):
    response = client.post("/api/notebooks", json={"title": "Targets", "cells": [{"kind": "sql", "source": "SELECT * FROM silver_player_season"}], **extra})
    assert response.status_code == 201, response.text
    return response.json()


def editable(doc):
    return {k: doc[k] for k in ("title", "cells", "origin", "version")}


def test_crud_versions_and_atomic_writes(notebook_environment, monkeypatch):
    original = os.replace
    replaced = []
    def replace(src, dst):
        assert Path(src).parent == Path(dst).parent == notebook_environment
        json.loads(Path(src).read_text())
        replaced.append(dst)
        original(src, dst)
    monkeypatch.setattr(os, "replace", replace)
    doc = create(origin={"kind": "board", "ref": "board-123"})
    assert len(doc["id"]) == 32 and doc["version"] == 1
    assert doc["created_at"] == doc["updated_at"]
    assert client.get(f'/api/notebooks/{doc["id"]}').json() == doc
    assert client.get("/api/notebooks").json()["notebooks"] == [doc]
    body = {**editable(doc), "title": "Updated"}
    updated = client.put(f'/api/notebooks/{doc["id"]}', json=body)
    assert updated.status_code == 200
    assert updated.json()["version"] == 2 and updated.json()["title"] == "Updated"
    assert updated.json()["created_at"] == doc["created_at"]
    assert client.put(f'/api/notebooks/{doc["id"]}', json=body).status_code == 409
    assert len(replaced) == 2 and not list(notebook_environment.glob("*.tmp"))
    assert client.delete(f'/api/notebooks/{doc["id"]}').status_code == 204
    assert client.get(f'/api/notebooks/{doc["id"]}').status_code == 404
    assert client.get("/api/notebooks").json() == {"notebooks": []}


def test_concurrent_updates_have_one_winner():
    doc = create()
    def update(_):
        return client.put(f'/api/notebooks/{doc["id"]}', json=editable(doc)).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(update, range(2))) == [200, 409]


@pytest.mark.parametrize("notebook_id", ["not-an-id", "..%2Fescape", "%2Fetc%2Fpasswd", "a" * 32])
def test_invalid_or_unknown_ids_cannot_read_write_or_delete(notebook_id):
    url = f"/api/notebooks/{notebook_id}"
    assert client.get(url).status_code == 404
    assert client.put(url, json={"version": 1}).status_code == 404
    assert client.delete(url).status_code == 404


def test_caller_cannot_choose_notebook_id_and_cell_ids_are_unique():
    assert client.post("/api/notebooks", json={"id": uuid4().hex}).status_code == 422
    assert client.post("/api/notebooks", json={"version": 99}).status_code == 422
    assert client.post("/api/notebooks", json={"cells": [{"id": "../escape", "kind": "sql"}]}).status_code == 422
    cell = {"id": uuid4().hex, "kind": "markdown", "source": "hello"}
    assert client.post("/api/notebooks", json={"cells": [cell, cell]}).status_code == 400


def test_symlink_file_and_directory_rejected(notebook_environment, tmp_path, monkeypatch):
    doc = create()
    path = notebook_environment / f'{doc["id"]}.json'
    path.unlink()
    outside = tmp_path / "outside.json"
    outside.write_text('{"private":true}')
    path.symlink_to(outside)
    assert client.get(f'/api/notebooks/{doc["id"]}').status_code == 404
    assert client.delete(f'/api/notebooks/{doc["id"]}').status_code == 404
    link = tmp_path / "alias"
    link.symlink_to(notebook_environment, target_is_directory=True)
    monkeypatch.setenv("DIME_NOTEBOOK_DIR", str(link))
    assert client.post("/api/notebooks", json={}).status_code == 400
    assert outside.read_text() == '{"private":true}'


@pytest.mark.parametrize("outputs", [
    {"columns": [{"name": "value", "type": "VARCHAR"}], "rows": [{"value": "x" * 1024}] * 1000},
    {"figures": [{"data": "x" * (OUTPUT_CAP + 1)}]},
])
def test_output_caps_keep_only_preview_and_count(outputs):
    doc = create(cells=[{"kind": "python", "source": "show(df)", "outputs": outputs}])
    output = doc["cells"][0]["outputs"]
    assert output["truncated"] is True
    assert len(json.dumps(output).encode()) < OUTPUT_CAP
    if "rows" in outputs:
        assert output["row_count"] == 1000 and len(output["rows"]) == 20
    assert client.get(f'/api/notebooks/{doc["id"]}').json() == doc


def test_exports_preserve_sources():
    doc = create(cells=[{"kind": "markdown", "source": "# Heading"}, {"kind": "sql", "source": "SELECT 1"}, {"kind": "python", "source": "print(1)"}])
    url = f'/api/notebooks/{doc["id"]}/export'
    assert client.get(url + "?fmt=json").json() == doc
    exported = client.get(url + "?fmt=ipynb")
    assert "attachment" in exported.headers["content-disposition"]
    nb = exported.json()
    assert nb["nbformat"] == 4
    assert [c["cell_type"] for c in nb["cells"]] == ["markdown", "code", "code"]
    assert "".join(nb["cells"][1]["source"]) == "%%sql\nSELECT 1"
    assert nb["cells"][2]["outputs"] == []
    assert client.get(url + "?fmt=invalid").status_code == 422


def test_nested_python_outputs_keep_table_row_counts():
    outputs = {"tables": [{"rows": [{"value": "x" * 1024}] * 500, "row_count": 900}],
               "stdout": "done", "figures": []}
    doc = create(cells=[{"kind": "python", "source": "df", "outputs": outputs}])
    preview = doc["cells"][0]["outputs"]
    assert preview["truncated"] and preview["tables"][0]["row_count"] == 900
    assert len(preview["tables"][0]["rows"]) == 20


@pytest.mark.parametrize("rows,truncated", [([], False), ([{"Team": "A|B\n<script>", "Rating": None}], True)])
def test_snapshot_export_is_a_markdown_table(rows, truncated):
    doc = create(cells=[{"kind": "markdown", "source": "## Snapshot", "outputs": {
        "kind": "snapshot", "data": {"columns": [{"name": "Team", "type": "VARCHAR"}, {"name": "Rating", "type": "DOUBLE"}], "rows": rows, "truncated": truncated},
    }}])
    exported = client.get(f'/api/notebooks/{doc["id"]}/export?fmt=ipynb').json()["cells"][0]
    assert exported["cell_type"] == "markdown"
    assert "outputs" not in exported
    source = "".join(exported["source"])
    assert "## Snapshot" in source
    assert f'Cached snapshot · from answer · {doc["created_at"]}' in source
    assert "| Team | Rating |\n| --- | --- |" in source
    if rows:
        assert "| A&#124;B<br>&lt;script&gt; | — |" in source
        assert "Bounded preview" in source
    assert client.get(f'/api/notebooks/{doc["id"]}').json()["cells"][0]["outputs"]["data"]["rows"] == rows


def query(statement="SELECT player_id, player, ppg FROM silver_player_season ORDER BY player_id", **extra):
    return client.post("/api/notebooks/sql", json={"sql": statement, **extra})


def test_sql_typed_paging_and_ceiling():
    first = query(page_size=500)
    assert first.status_code == 200, first.text
    data = first.json()
    assert data["columns"] == [{"name": "player_id", "type": "BIGINT"}, {"name": "player", "type": "VARCHAR"}, {"name": "ppg", "type": "DOUBLE"}]
    assert data["rows"][0]["player_id"] == 0 and len(data["rows"]) == 500
    assert data["page"] == 0 and data["has_more"] and data["truncated"] and data["ms"] >= 0
    second = query(page=1, page_size=500).json()
    assert second["rows"][0]["player_id"] == 500
    last = query(page=9, page_size=500).json()
    assert last["rows"][-1]["player_id"] == 4999 and not last["has_more"] and last["truncated"]
    assert query(page=10, page_size=500).status_code == 422


def test_sql_named_params_and_empty_result():
    data = query("WITH picked AS (SELECT * FROM silver_player_season WHERE player_id=$id) SELECT player, ppg FROM picked", params={"id": 12}).json()
    assert data["rows"] == [{"player": "Player 12", "ppg": 1.2}]
    assert not data["has_more"] and not data["truncated"]
    empty = query("SELECT player FROM silver_player_season WHERE player=$name", params={"name": "' OR 1=1 --"}).json()
    assert empty["rows"] == [] and empty["columns"] == [{"name": "player", "type": "VARCHAR"}]
    assert query("SELECT $missing FROM silver_player_season").status_code == 400


@pytest.mark.parametrize("predicate", [
    "player_id = 12 AND ppg > 1",
    "player_id = 12 OR player_id = -1",
    "NOT (player_id <> 12)",
    "player_id BETWEEN 12 AND 12",
    "player_id IN (12)",
    "player_id NOT IN (0, 1) AND player_id BETWEEN 12 AND 12",
    "CASE WHEN player_id = 12 AND ppg > 1 THEN TRUE ELSE FALSE END",
    "player LIKE 'Player 12'",
])
def test_notebook_sql_operators(predicate):
    response = query(f"SELECT player_id FROM silver_player_season WHERE {predicate}")
    assert response.status_code == 200, response.text
    assert response.json()["rows"] == [{"player_id": 12}]


def test_sql_empty_statement_and_nonfinite_values():
    assert query(";").status_code == 400
    assert query(" ").status_code == 400
    data = query("SELECT 'NaN'::DOUBLE AS value FROM silver_player_season LIMIT 1").json()
    assert data["rows"] == [{"value": None}]


def test_sql_nested_nonfinite_values_are_json_safe():
    response = query("""SELECT
        ['NaN'::DOUBLE, 'Infinity'::DOUBLE, '-Infinity'::DOUBLE, 1.5] AS numbers,
        {'nested': [{'value': 'NaN'::DOUBLE}, {'value': 2.5}]} AS details
        FROM silver_player_season LIMIT 1""")
    assert response.status_code == 200, response.text
    assert response.json()["rows"] == [{
        "numbers": [None, None, None, 1.5],
        "details": {"nested": [{"value": None}, {"value": 2.5}]},
    }]
    json.dumps(response.json(), allow_nan=False)


@pytest.mark.parametrize("statement", [
    "INSERT INTO silver_player_season VALUES (7000, 'Injected', 1)",
    "UPDATE silver_player_season SET ppg=0",
    "CREATE TABLE stolen (id INTEGER)",
    "ALTER TABLE silver_player_season ADD COLUMN stolen INTEGER",
    "PRAGMA table_info(silver_player_season)",
    "SET threads=1",
    "SELECT 1; DROP TABLE silver_player_season",
    "WITH changed AS (DELETE FROM silver_player_season RETURNING *) SELECT * FROM changed",
    "SELECT CASE WHEN TRUE THEN (DELETE FROM silver_player_season RETURNING player_id) ELSE 0 END",
    "SELECT * FROM silver_player_season WHERE TRUE AND (UPDATE silver_player_season SET ppg=0 RETURNING TRUE)",
    "DELETE FROM silver_player_season", "DROP TABLE silver_player_season",
    "SELECT * FROM private_notes", "SELECT * FROM unknown_table",
    "SELECT * FROM read_csv('/etc/passwd')", "SELECT * FROM read_parquet('https://example.com/x')",
    "SELECT read_blob('/etc/passwd') FROM silver_player_season",
    "COPY silver_player_season TO '/tmp/notebook.csv'", "ATTACH '/tmp/test.db' AS other",
    "SELECT 1; SELECT 2", "SELECT * INTO stolen FROM silver_player_season",
    "WITH silver_player_season AS (SELECT 1) SELECT * FROM silver_player_season",
])
def test_sql_rejects_unsafe_or_unknown_queries(statement):
    assert query(statement).status_code == 400
    check = query("SELECT COUNT(*) AS n, SUM(ppg) AS total FROM silver_player_season").json()
    assert check["rows"] == [{"n": 6000, "total": pytest.approx(1799700)}]


def test_sql_external_access_is_disabled():
    with sql.connection() as con:
        assert con.execute("SELECT current_setting('enable_external_access')").fetchone()[0] is False
        with pytest.raises(duckdb.Error):
            con.execute("SELECT * FROM read_csv('/etc/passwd')")


def test_sql_after_pooled_warehouse_read_keeps_external_access_blocked():
    try:
        with warehouse_store.connect(read_only=True) as pooled:
            assert pooled.execute("SELECT COUNT(*) FROM silver_player_season").fetchone()[0] == 6000
        response = query(page_size=1)
        assert response.status_code == 200, response.text
        assert response.json()["rows"][0]["player_id"] == 0
        with sql.connection() as con:
            assert con.execute("SELECT current_setting('enable_external_access')").fetchone()[0] is False
            with pytest.raises(duckdb.Error, match="disabled"):
                con.execute("SELECT * FROM read_csv('/etc/passwd')")
        with warehouse_store.connect(read_only=True) as pooled:
            assert pooled.execute("SELECT COUNT(*) FROM silver_player_season").fetchone()[0] == 6000
    finally:
        warehouse_store.warehouse_pool_clear()


def test_sql_allowlist_fails_closed(monkeypatch):
    from shared.tools import league
    monkeypatch.setattr(league, "_SQL_TABLES", [])
    assert query().status_code == 400
    monkeypatch.delattr(league, "_SQL_TABLES")
    assert query().status_code == 503


def test_sql_caps_and_timeout(monkeypatch):
    assert query(page_size=501).status_code == 422
    assert query(page=-1).status_code == 422
    def timeout(*args, **kwargs):
        raise TimeoutError("query exceeded 30s")
    monkeypatch.setattr(sql, "_run_with_timeout", timeout)
    assert query().status_code == 408


def python(source, **extra):
    return client.post("/api/notebooks/python", json={"source": source, **extra})


def test_python_disabled_by_default_and_capability(monkeypatch):
    assert client.get("/api/notebooks/capabilities").json()["python"]["enabled"] is False
    response = python("print('no')")
    assert response.status_code == 403 and "DIME_NOTEBOOK_PYTHON=1" in response.json()["detail"]
    monkeypatch.setenv("DIME_NOTEBOOK_PYTHON", "1")
    assert client.get("/api/notebooks/capabilities").json()["python"]["enabled"] is True
    assert python("pass", timeout_s=61).status_code == 422


def test_python_stdout_stderr_dataframe_and_statelessness(monkeypatch):
    monkeypatch.setenv("DIME_NOTEBOOK_PYTHON", "1")
    source = "import sys\nprint('hello')\nprint('warning', file=sys.stderr)\nx = 42\nsql('SELECT player_id, ppg FROM silver_player_season WHERE player_id=$id', id=12)"
    response = python(source)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"], data
    assert "hello" in data["stdout"] and "warning" in data["stderr"]
    assert data["tables"][0]["rows"] == [{"player_id": 12, "ppg": 1.2}]
    assert data["tables"][0]["columns"][0]["name"] == "player_id"
    assert python("print(x)").json()["ok"] is False


def test_python_sql_infers_columns_after_null_leading_rows(monkeypatch):
    monkeypatch.setenv("DIME_NOTEBOOK_PYTHON", "1")
    result = python("sql('SELECT CASE WHEN player_id < 150 THEN NULL ELSE player_id END AS value FROM silver_player_season WHERE player_id <= 150 ORDER BY player_id')").json()
    assert result["ok"], result
    table = result["tables"][0]
    assert table["columns"] == [{"name": "value", "type": "Int64"}]
    assert table["row_count"] == 151
    assert table["rows"][:150] == [{"value": None}] * 150
    assert table["rows"][150] == {"value": 150}


def test_python_show_dataframe_stdout_cap_and_table_cap(monkeypatch):
    monkeypatch.setenv("DIME_NOTEBOOK_PYTHON", "1")
    result = python("print('x' * 100000)\nshow(pl.DataFrame({'value': range(700)}))").json()
    assert result["ok"], result
    assert len(result["stdout"]) == 65536
    assert len(result["tables"][0]["rows"]) == 500
    assert result["tables"][0]["row_count"] == 700 and result["tables"][0]["truncated"]


@pytest.mark.parametrize("theme,foreground", [("dark", "#8a9099"), ("light", "#737982")])
def test_python_figure(monkeypatch, theme, foreground):
    import io
    from PIL import Image

    monkeypatch.setenv("DIME_NOTEBOOK_PYTHON", "1")
    result = python("import matplotlib.pyplot as plt\nplt.plot([1,2,3], [2,1,4])\nplt.title('Notebook')\nprint(plt.rcParams['text.color'])\nprint(plt.rcParams['axes.spines.top'], plt.rcParams['axes.spines.right'])", theme=theme).json()
    assert result["ok"], result
    png = base64.b64decode(result["figures"][0]["data"])
    assert png.startswith(b'\x89PNG\r\n\x1a\n') and len(png) <= 1024 * 1024
    assert foreground in result["stdout"] and "False False" in result["stdout"]
    assert Image.open(io.BytesIO(png)).getpixel((0, 0))[3] == 0


def test_python_theme_validation(monkeypatch):
    monkeypatch.setenv("DIME_NOTEBOOK_PYTHON", "1")
    assert python("pass", theme="unknown").status_code == 422


def test_missing_matplotlib_is_a_capture_warning(monkeypatch):
    from v2.notebooks.worker import plotting
    monkeypatch.setitem(sys.modules, "matplotlib", None)
    warnings = []
    assert plotting(warnings) is None
    assert "Figure capture is unavailable" in warnings[0]


def test_python_env_no_secrets_isolated_cwd_and_traceback(monkeypatch):
    monkeypatch.setenv("DIME_NOTEBOOK_PYTHON", "1")
    monkeypatch.setenv("NOTEBOOK_SENTINEL_SECRET", "do-not-inherit")
    result = python("import os, sys\nprint(os.getenv('NOTEBOOK_SENTINEL_SECRET'))\nprint(sys.flags.isolated)\nprint(os.getcwd())\nraise ValueError('expected failure')").json()
    assert result["ok"] is False and "do-not-inherit" not in json.dumps(result)
    assert "None\n1\n" in result["stdout"] and "dime-notebook-" in result["stdout"]
    assert "Traceback" in result["error"] and "ValueError: expected failure" in result["error"]


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group assertion")
def test_python_timeout_kills_child_process(monkeypatch, tmp_path):
    monkeypatch.setenv("DIME_NOTEBOOK_PYTHON", "1")
    pidfile = tmp_path / "child.pid"
    source = f"import subprocess, sys, time\np = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\nopen({str(pidfile)!r}, 'w').write(str(p.pid))\nprint('before timeout')\ntime.sleep(60)"
    result = python(source, timeout_s=8).json()
    assert result["timed_out"] and result["ok"] is False
    assert "before timeout" in result["stdout"]
    assert pidfile.exists(), result
    pid = int(pidfile.read_text())
    proc = Path(f"/proc/{pid}/stat")
    if proc.exists():
        assert proc.read_text().split()[2] == "Z"
    else:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


def test_python_sql_is_read_only_and_rejects_file_functions(monkeypatch):
    monkeypatch.setenv("DIME_NOTEBOOK_PYTHON", "1")
    result = python("sql(\"SELECT * FROM read_csv('/etc/passwd')\")").json()
    assert result["ok"] is False and "blocked" in result["error"]
