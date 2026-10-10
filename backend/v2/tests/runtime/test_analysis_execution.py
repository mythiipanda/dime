import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from v2.contracts import EvidenceEnvelope
from v2.runtime.analysis_execution import (
    AnalysisRequest,
    build_envelope,
    execute_analysis,
)

PREDECESSOR_MODULE = (
    Path(__file__).resolve().parent
    / "_negctrl"
    / "predecessor_analysis_execution.py"
)


def make_fixture(path, total=200):
    if path.exists():
        path.unlink()
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE silver_smoke(id INTEGER, pts DOUBLE)")
    con.executemany(
        "INSERT INTO silver_smoke VALUES (?, ?)",
        [(i, float(i) * 1.5) for i in range(1, total + 1)],
    )
    con.execute("CREATE TABLE secret_table(s VARCHAR)")
    con.execute("INSERT INTO secret_table VALUES ('SECRET')")
    con.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_request(tmp_path, sql, sha, **changes):
    values = dict(
        run_id="run-ha02",
        node_id="node-sql",
        sql=sql,
        input_path=str(tmp_path / "fixture.duckdb"),
        input_sha256=sha,
        artifact_dir=str(tmp_path / "artifacts"),
        deadline_s=20.0,
        row_cap=25,
        byte_cap=65536,
        allowed_tables=("silver_smoke",),
    )
    values.update(changes)
    return AnalysisRequest(**values)


def test_success_sum_literal_matches_expected(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(tmp_path, "SELECT SUM(pts) AS total FROM silver_smoke", sha)
    result = execute_analysis(request)
    assert result.status == "success"
    assert result.columns == ("total",)
    assert result.rows == [[30150.0]]
    assert result.error is None
    assert result.dead is True
    assert result.pid is not None


def test_runaway_query_times_out_with_dead_pid(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(
        tmp_path,
        "WITH RECURSIVE t(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM t)"
        " SELECT COUNT(*) FROM t",
        sha,
        deadline_s=2.0,
    )
    result = execute_analysis(request)
    assert result.status == "timeout"
    assert result.pid is not None
    assert result.dead is True


def test_external_access_blocked_by_duckdb(tmp_path):
    payloads = [
        "SELECT * FROM read_csv('C:/nope/missing.csv')",
        "ATTACH ':memory:' AS extra_db",
        "COPY (SELECT 1 AS a) TO 'C:/nope/out.csv'",
        "INSTALL definitely_not_an_ext_xyz",
        "LOAD definitely_not_an_ext_xyz",
        "SELECT * FROM read_csv('http://127.0.0.1:9/x.csv')",
    ]
    sha = make_fixture(tmp_path / "fixture.duckdb")
    for sql in payloads:
        request = make_request(tmp_path, sql, sha)
        result = execute_analysis(request)
        assert result.status == "execution_failed", sql
        assert result.error is not None, sql
        assert "duckdb" in result.error.lower(), sql


def test_unauthorized_table_policy_rejected(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(tmp_path, "SELECT * FROM silver_missing", sha)
    result = execute_analysis(request)
    assert result.status == "policy_rejected"
    assert result.rows is None
    assert result.pid is None


def test_quoted_table_reference_policy_rejected(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(tmp_path, 'SELECT * FROM "secret_table"', sha)
    result = execute_analysis(request)
    assert result.status == "policy_rejected"
    assert result.rows is None
    assert result.pid is None
    assert result.error is not None
    assert "secret_table" in result.error


def test_single_quoted_table_reference_policy_rejected(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(tmp_path, "SELECT * FROM 'secret_table'", sha)
    result = execute_analysis(request)
    assert result.status == "policy_rejected"
    assert result.rows is None
    assert result.pid is None
    assert "secret_table" in result.error


def test_function_form_table_reference_policy_rejected(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(
        tmp_path, "SELECT * FROM query_table('secret_table')", sha
    )
    result = execute_analysis(request)
    assert result.status == "policy_rejected"
    assert result.rows is None
    assert result.pid is None
    assert "secret_table" in result.error


def test_join_quoted_table_reference_policy_rejected(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(
        tmp_path,
        'SELECT silver_smoke.id FROM silver_smoke JOIN "secret_table" ON true',
        sha,
    )
    result = execute_analysis(request)
    assert result.status == "policy_rejected"
    assert result.rows is None
    assert result.pid is None
    assert "secret_table" in result.error


def test_allowed_quoted_table_still_succeeds(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(
        tmp_path,
        'SELECT SUM(pts) AS total FROM "silver_smoke"',
        sha,
    )
    result = execute_analysis(request)
    assert result.status == "success"
    assert result.rows == [[30150.0]]


def test_write_statement_policy_rejected(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    for sql in (
        "DELETE FROM silver_smoke",
        "INSERT INTO secret_table VALUES ('x')",
        "UPDATE secret_table SET s = 'x'",
        "DROP TABLE secret_table",
        "CREATE TABLE evil(x INTEGER)",
    ):
        request = make_request(tmp_path, sql, sha)
        result = execute_analysis(request)
        assert result.status == "policy_rejected", sql
        assert result.rows is None, sql
        assert result.pid is None, sql


def test_input_pin_mismatch_policy_rejected(tmp_path):
    make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(
        tmp_path, "SELECT 1 AS a", "0" * 64,
    )
    result = execute_analysis(request)
    assert result.status == "policy_rejected"
    assert result.rows is None
    assert result.pid is None


def test_row_cap_truncates_with_flag(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(
        tmp_path, "SELECT id FROM silver_smoke ORDER BY id", sha, row_cap=3
    )
    result = execute_analysis(request)
    assert result.status == "success"
    assert result.rows == [[1], [2], [3]]
    assert result.row_cap_hit is True


def test_byte_cap_truncates_with_flag(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(
        tmp_path,
        "SELECT id FROM silver_smoke ORDER BY id",
        sha,
        row_cap=200,
        byte_cap=40,
    )
    result = execute_analysis(request)
    assert result.status == "success"
    assert result.truncated is True
    assert len(json.dumps(result.rows)) <= 40
    assert len(result.rows) < 200


def test_envelope_valid_with_preserved_lineage(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(tmp_path, "SELECT SUM(pts) AS total FROM silver_smoke", sha)
    result = execute_analysis(request)
    assert result.status == "success"
    envelope = build_envelope(
        result,
        evidence_id="ha02-smoke",
        capability="analysis_execution",
        source="duckdb:fixture.duckdb",
        observed_at=datetime(2026, 10, 10, 12, tzinfo=UTC),
    )
    assert isinstance(envelope, EvidenceEnvelope)
    assert envelope.rows == [{"total": 30150.0}]
    assert any("run-ha02" in entry for entry in envelope.lineage)
    assert any("node-sql" in entry for entry in envelope.lineage)
    assert any(sha[:16] in entry for entry in envelope.lineage)


def test_cancel_kills_child_with_dead_pid(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(
        tmp_path,
        "WITH RECURSIVE t(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM t)"
        " SELECT COUNT(*) FROM t",
        sha,
        deadline_s=30.0,
    )
    cancel = threading.Event()
    outcome = {}

    def runner():
        outcome["result"] = execute_analysis(request, cancel_event=cancel)

    worker = threading.Thread(target=runner, daemon=True)
    worker.start()
    assert cancel.wait(0.2) is False
    cancel.set()
    worker.join(timeout=30.0)
    assert "result" in outcome
    assert outcome["result"].status == "cancelled"
    assert outcome["result"].dead is True


def test_no_python_exec_exposure_in_module():
    import inspect

    import v2.runtime.analysis_execution as module

    src = inspect.getsource(module)
    for token in ("exec(", "eval(", "compile(", "__builtins__"):
        assert token not in src


def test_memory_limit_configured_and_success(tmp_path, monkeypatch):
    import v2.runtime.analysis_execution as module

    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(
        tmp_path,
        "SELECT SUM(pts) AS total FROM silver_smoke",
        sha,
        memory_limit_bytes=256 * 1024 * 1024,
    )
    observed = []
    real_create = module._create_job

    def tracking_create(limit):
        outcome = real_create(limit)
        observed.append((limit, outcome[1]))
        return outcome

    monkeypatch.setattr(module, "_create_job", tracking_create)
    result = execute_analysis(request)
    assert observed, "memory limit never reached the job constructor"
    assert observed[0][0] == 256 * 1024 * 1024
    assert result.status == "success"
    assert result.rows == [[30150.0]]
    assert "established" in result.enforcement.job_object


def test_os_rejected_memory_limit_returns_unsupported(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(
        tmp_path,
        "SELECT SUM(pts) AS total FROM silver_smoke",
        sha,
        memory_limit_bytes=1024,
    )
    result = execute_analysis(request)
    assert result.status == "unsupported"
    assert result.rows is None
    assert result.pid is None
    assert result.enforcement.job_object is not None
    assert "unsupported" in result.enforcement.job_object


def test_unsupported_enforcement_is_fail_closed(tmp_path, monkeypatch):
    import v2.runtime.analysis_execution as module

    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(tmp_path, "SELECT 1 AS a", sha)
    monkeypatch.setattr(module, "_create_job", lambda limit: (None, "unsupported: test"))
    result = execute_analysis(request)
    assert result.status == "unsupported"
    assert result.rows is None
    assert result.pid is None
    assert "unsupported" in result.enforcement.job_object


def test_job_assignment_failure_returns_execution_failed(tmp_path, monkeypatch):
    import v2.runtime.analysis_execution as module

    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(tmp_path, "SELECT 1 AS a", sha)
    monkeypatch.setattr(module, "_assign_to_job", lambda job, proc: False)
    result = execute_analysis(request)
    assert result.status == "execution_failed"
    assert result.rows is None
    assert result.error is not None
    assert "job" in result.error.lower()
    assert result.dead is True


def test_comma_separated_unauthorized_table_policy_rejected(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(
        tmp_path,
        "SELECT * FROM silver_smoke, secret_table",
        sha,
    )
    result = execute_analysis(request)
    assert result.status == "policy_rejected"
    assert result.rows is None
    assert result.pid is None
    assert "secret_table" in result.error


def test_schema_qualified_unauthorized_table_policy_rejected(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(tmp_path, "SELECT * FROM main.secret_table", sha)
    result = execute_analysis(request)
    assert result.status == "policy_rejected"
    assert result.rows is None
    assert result.pid is None
    assert "secret_table" in result.error


def test_schema_qualified_allowed_table_succeeds(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(
        tmp_path,
        "SELECT SUM(pts) AS total FROM main.silver_smoke",
        sha,
    )
    result = execute_analysis(request)
    assert result.status == "success"
    assert result.rows == [[30150.0]]


def test_subquery_unauthorized_table_policy_rejected(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(
        tmp_path,
        "SELECT COUNT(*) AS n FROM (SELECT * FROM secret_table) AS sub",
        sha,
    )
    result = execute_analysis(request)
    assert result.status == "policy_rejected"
    assert result.rows is None
    assert result.pid is None
    assert "secret_table" in result.error


def test_function_form_external_file_reaches_duckdb(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(
        tmp_path,
        "SELECT * FROM read_csv('C:/nope/missing.csv')",
        sha,
    )
    result = execute_analysis(request)
    assert result.status == "execution_failed"
    assert result.error is not None
    assert "duckdb" in result.error.lower()


def test_predecessor_negative_control_fails():
    pred_src = PREDECESSOR_MODULE.read_text(encoding="utf-8")
    assert "SetInformationJobObject" not in pred_src
    assert "JOBOBJECT_EXTENDED_LIMIT_INFORMATION" not in pred_src
    assert "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" not in pred_src
    assert 'FROM\\s+([A-Za-z_][\\w]*)' in pred_src
    assert "_assign_to_job(job, proc)" in pred_src
