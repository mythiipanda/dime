import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest
from sqlglot import exp, parse

from v2.contracts import EvidenceEnvelope

PREDECESSOR_MODULE = (
    Path(__file__).resolve().parent
    / "_negctrl"
    / "predecessor_analysis_execution.py"
)

BASE_352C3644_MODULE = (
    Path(__file__).resolve().parent
    / "_negctrl"
    / "base_352c3644_analysis_execution.py"
)

SECRET = "SECRET"
ALLOWED = ("silver_smoke",)


def test_parser_walker_resolves_aliases_and_ctes():
    tree = parse("SELECT * FROM silver_smoke a, secret_table b", dialect="duckdb")
    assert tree
    names = [t.name for e in tree if e is not None for t in e.find_all(exp.Table)]
    assert "silver_smoke" in names
    assert "secret_table" in names

    laundered = parse(
        "WITH secret_table AS (SELECT 1 AS x) SELECT * FROM main.secret_table",
        dialect="duckdb",
    )
    assert laundered
    assert laundered[0] is not None
    tables = list(laundered[0].find_all(exp.Table))
    assert len(tables) == 1
    assert tables[0].name == "secret_table"
    assert tables[0].db == "main"


def test_predecessor_negative_control_fails(tmp_path):
    pred_src = PREDECESSOR_MODULE.read_text(encoding="utf-8")
    assert "SetInformationJobObject" not in pred_src
    assert "JOBOBJECT_EXTENDED_LIMIT_INFORMATION" not in pred_src
    assert "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" not in pred_src
    assert 'FROM\\s+([A-Za-z_][\\w]*)' in pred_src
    assert "_assign_to_job(job, proc)" in pred_src
