import hashlib
import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from v2.contracts import EvidenceEnvelope
from v2.runtime.analysis_execution import (
    AnalysisRequest,
    build_envelope,
    execute_analysis,
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


def test_non_select_policy_rejected(tmp_path):
    sha = make_fixture(tmp_path / "fixture.duckdb")
    request = make_request(tmp_path, "DELETE FROM silver_smoke", sha)
    result = execute_analysis(request)
    assert result.status == "policy_rejected"
    assert result.rows is None
    assert result.pid is None


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


def test_predecessor_negative_control_fails():
    import inspect

    import shared.store as store
    import shared.tools.league as league

    repo = Path("C:/Users/15980/Downloads/dime/hermes-isolation-sql")
    shared_src = (repo / "backend/shared/tools/shared.py").read_text(encoding="utf-8")
    assert "exec(compile" in shared_src
    assert "__builtins__" in shared_src
    assert "pass" in inspect.getsource(store._PooledConnection.close)
    timeout_src = inspect.getsource(league._execute_with_timeout)
    assert "daemon=True" in timeout_src
    assert "pid" not in timeout_src.lower()


def test_no_python_exec_exposure_in_module():
    repo = Path("C:/Users/15980/Downloads/dime/hermes-isolation-sql")
    src = (repo / "backend/v2/runtime/analysis_execution.py").read_text(encoding="utf-8")
    for token in ("exec(", "eval(", "compile(", "__builtins__"):
        assert token not in src


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
