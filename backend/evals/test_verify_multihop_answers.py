import json
import os
import subprocess
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCRIPT = REPO_ROOT / "backend" / "evals" / "verify_multihop_answers.py"
SCRIPT = Path(os.environ.get("VERIFY_MULTIHOP_SCRIPT") or DEFAULT_SCRIPT)


def run_records(directory, records, name="records.jsonl"):
    warehouse = directory / (name + ".duckdb")
    duckdb.connect(str(warehouse)).close()
    records_path = directory / name
    records_path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(records_path), str(warehouse)],
        capture_output=True,
        text=True,
        timeout=120,
    )


def entry(name, sql):
    return {"name": name, "sql": sql}


def test_scope_line_states_limits(tmp_path):
    run = run_records(tmp_path, [{"task_id": "row", "answer": "7", "verification_sql": "SELECT 7"}])
    assert run.returncode == 0
    assert "SCOPE" in run.stdout
    assert "binding not certified" in run.stdout
    assert "rows=1 failures=0" in run.stdout


def test_multirow_result_is_checked(tmp_path):
    run = run_records(tmp_path, [{
        "task_id": "multirow",
        "answer": "7 and 12",
        "expected_paths": [entry("fixture", "SELECT * FROM (VALUES (7), (12))")],
    }])
    assert run.returncode == 0
    assert "rows=1 failures=0" in run.stdout
    assert "-> 7 | 12" in run.stdout


def test_multipath_answer_is_supported(tmp_path):
    run = run_records(tmp_path, [{
        "task_id": "paths",
        "answer": "7 and 12",
        "expected_paths": [entry("first", "SELECT 7"), entry("second", "SELECT 12")],
    }])
    assert run.returncode == 0
    assert "rows=1 failures=0" in run.stdout
    assert "-> 7" in run.stdout
    assert "-> 12" in run.stdout


def test_token_may_be_supplied_by_any_path(tmp_path):
    run = run_records(tmp_path, [{
        "task_id": "union",
        "answer": "7",
        "expected_paths": [entry("first", "SELECT 70"), entry("second", "SELECT 7")],
    }])
    assert run.returncode == 0
    assert "rows=1 failures=0" in run.stdout


def test_seven_does_not_match_seventy(tmp_path):
    run = run_records(tmp_path, [{
        "task_id": "wrong",
        "answer": "7",
        "expected_paths": [entry("fixture", "SELECT 70")],
    }])
    assert run.returncode == 1
    assert "rows=1 failures=1" in run.stdout
    assert "MISSING VALUE 7" in run.stdout


def test_close_integers_are_not_treated_as_equal(tmp_path):
    run = run_records(tmp_path, [{
        "task_id": "teamid",
        "answer": "1610612743",
        "expected_paths": [entry("fixture", "SELECT 1610612744")],
    }])
    assert run.returncode == 1
    assert "MISSING VALUE 1610612743" in run.stdout


def test_negative_answer_requires_negative_evidence(tmp_path):
    run = run_records(tmp_path, [{
        "task_id": "sign_bad",
        "answer": "-7",
        "expected_paths": [entry("fixture", "SELECT 7")],
    }])
    assert run.returncode == 1
    assert "MISSING VALUE -7" in run.stdout
    run = run_records(tmp_path, [{
        "task_id": "sign_ok",
        "answer": "-7",
        "expected_paths": [entry("fixture", "SELECT -7")],
    }], name="sign_ok.jsonl")
    assert run.returncode == 0
    assert "rows=1 failures=0" in run.stdout


def test_leading_decimal_literal_is_matched_exactly(tmp_path):
    run = run_records(tmp_path, [{
        "task_id": "dotfive_bad",
        "answer": ".5",
        "expected_paths": [entry("fixture", "SELECT 5")],
    }])
    assert run.returncode == 1
    assert "MISSING VALUE 0.5" in run.stdout
    run = run_records(tmp_path, [{
        "task_id": "dotfive_ok",
        "answer": ".5",
        "expected_paths": [entry("fixture", "SELECT 0.5")],
    }], name="dotfive_ok.jsonl")
    assert run.returncode == 0
    assert "rows=1 failures=0" in run.stdout
    assert "-> 0.5" in run.stdout


def test_nearby_decimal_value_is_not_accepted(tmp_path):
    run = run_records(tmp_path, [{
        "task_id": "near_bad",
        "answer": "7.1",
        "expected_paths": [entry("fixture", "SELECT 7.1000000001")],
    }])
    assert run.returncode == 1
    assert "MISSING VALUE 7.1" in run.stdout
    run = run_records(tmp_path, [{
        "task_id": "near_ok",
        "answer": "7.1",
        "expected_paths": [entry("fixture", "SELECT 7.1")],
    }], name="near_ok.jsonl")
    assert run.returncode == 0
    assert "rows=1 failures=0" in run.stdout


def test_large_integers_keep_full_precision(tmp_path):
    big = 12345678901234567890
    run = run_records(tmp_path, [{
        "task_id": "huge_bad",
        "answer": str(big),
        "expected_paths": [entry("fixture", "SELECT %d" % (big + 1))],
    }], name="huge_bad.jsonl")
    assert run.returncode == 1
    assert "MISSING VALUE %d" % big in run.stdout
    run = run_records(tmp_path, [{
        "task_id": "huge_ok",
        "answer": str(big),
        "expected_paths": [entry("fixture", "SELECT %d" % big)],
    }], name="huge_ok.jsonl")
    assert run.returncode == 0
    assert "rows=1 failures=0" in run.stdout


def test_thousands_grouping_is_one_value(tmp_path):
    run = run_records(tmp_path, [{
        "task_id": "grouped",
        "answer": "1,234",
        "expected_paths": [entry("fixture", "SELECT 1234")],
    }])
    assert run.returncode == 0
    assert "rows=1 failures=0" in run.stdout
    assert "-> 1234" in run.stdout


def test_comma_separated_list_is_not_gobbled(tmp_path):
    run = run_records(tmp_path, [{
        "task_id": "list_ok",
        "answer": "7,12",
        "expected_paths": [entry("first", "SELECT 7"), entry("second", "SELECT 12")],
    }])
    assert run.returncode == 0
    assert "rows=1 failures=0" in run.stdout
    run = run_records(tmp_path, [{
        "task_id": "list_bad",
        "answer": "7,12",
        "expected_paths": [entry("fixture", "SELECT 712")],
    }], name="list_bad.jsonl")
    assert run.returncode == 1
    assert "MISSING VALUE 7" in run.stdout
    assert "MISSING VALUE 12" in run.stdout


def test_empty_result_is_a_failure(tmp_path):
    run = run_records(tmp_path, [{
        "task_id": "empty",
        "answer": "7",
        "expected_paths": [entry("fixture", "SELECT 7 WHERE false")],
    }])
    assert run.returncode == 1
    assert "rows=1 failures=2" in run.stdout
    assert "EMPTY RESULT" in run.stdout
    assert "MISSING VALUE 7" in run.stdout


def test_sql_error_is_a_failure(tmp_path):
    run = run_records(tmp_path, [{
        "task_id": "broken",
        "answer": "7",
        "expected_paths": [entry("fixture", "SELECT * FROM missing_fixture")],
    }])
    assert run.returncode == 1
    assert "SQL ERROR" in run.stdout
    assert "rows=1 failures=2" in run.stdout
    assert "MISSING VALUE 7" in run.stdout


def test_row_without_usable_query_is_a_failure(tmp_path):
    run = run_records(tmp_path, [
        {"task_id": "no_query", "answer": "7"},
        {"task_id": "empty_paths", "answer": "8", "expected_paths": []},
    ])
    assert run.returncode == 1
    assert "rows=2 failures=2" in run.stdout
    assert "NO VERIFICATION QUERY" in run.stdout


def test_verification_sql_only_valid(tmp_path):
    run = run_records(tmp_path, [{"task_id": "vsql_ok", "answer": "7", "verification_sql": "SELECT 7"}])
    assert run.returncode == 0
    assert "rows=1 failures=0" in run.stdout
    assert "answer_check" in run.stdout


def test_verification_sql_only_wrong_value(tmp_path):
    run = run_records(tmp_path, [{"task_id": "vsql_wrong", "answer": "7", "verification_sql": "SELECT 70"}])
    assert run.returncode == 1
    assert "MISSING VALUE 7" in run.stdout


def test_verification_sql_empty_result(tmp_path):
    run = run_records(tmp_path, [{"task_id": "vsql_empty", "answer": "7", "verification_sql": "SELECT 7 WHERE false"}])
    assert run.returncode == 1
    assert "EMPTY RESULT" in run.stdout


def test_verification_sql_error(tmp_path):
    run = run_records(tmp_path, [{
        "task_id": "vsql_broken",
        "answer": "7",
        "verification_sql": "SELECT * FROM missing_fixture",
    }])
    assert run.returncode == 1
    assert "SQL ERROR" in run.stdout


def test_answer_value_missing_from_every_result(tmp_path):
    run = run_records(tmp_path, [{
        "task_id": "missing",
        "answer": "7 and 99",
        "expected_paths": [entry("first", "SELECT 7"), entry("second", "SELECT 7")],
    }])
    assert run.returncode == 1
    assert "rows=1 failures=1" in run.stdout
    assert "MISSING VALUE 99" in run.stdout


def test_scientific_notation_answer_is_reported_not_dropped(tmp_path):
    run = run_records(tmp_path, [{"task_id": "sci", "answer": "1e5", "verification_sql": "SELECT 100000"}])
    assert run.returncode == 1
    assert "rows=1 failures=1" in run.stdout
    assert "UNSUPPORTED NUMERIC LITERAL 1e5" in run.stdout


def test_malformed_expected_paths_fail_visibly(tmp_path):
    run = run_records(tmp_path, [
        {"task_id": "bad_paths_type", "answer": "7", "expected_paths": "SELECT 7"},
        {"task_id": "bad_paths_item", "answer": "7", "expected_paths": ["SELECT 7"]},
        {"task_id": "missing_sql", "answer": "7", "expected_paths": [{"name": "fixture"}]},
        {"task_id": "sql_not_string", "answer": "7", "expected_paths": [{"name": "fixture", "sql": 7}]},
        {"task_id": "blank_sql", "answer": "7", "expected_paths": [{"name": "fixture", "sql": "   "}]},
    ])
    assert run.returncode == 1
    assert "rows=5 failures=10" in run.stdout
    assert "MALFORMED expected_paths" in run.stdout
    assert "MALFORMED SQL" in run.stdout
    assert "NO VERIFICATION QUERY" in run.stdout
    assert "MISSING VALUE 7" in run.stdout


def test_malformed_verification_sql_fails_visibly(tmp_path):
    run = run_records(tmp_path, [
        {"task_id": "vsql_type", "answer": "7", "verification_sql": 7},
        {"task_id": "vsql_blank", "answer": "7", "verification_sql": "  "},
    ])
    assert run.returncode == 1
    assert "rows=2 failures=4" in run.stdout
    assert "MALFORMED verification_sql" in run.stdout


def test_non_numeric_answer_is_not_failed(tmp_path):
    run = run_records(tmp_path, [{
        "task_id": "refusal",
        "answer": "no typed ranking arguments were supplied",
        "expected_paths": [entry("fixture", "SELECT 'intake required team_ratings evidence'")],
    }])
    assert run.returncode == 0
    assert "rows=1 failures=0" in run.stdout


def test_unreadable_row_fails_visibly(tmp_path):
    warehouse = tmp_path / "mixed.jsonl.duckdb"
    duckdb.connect(str(warehouse)).close()
    records_path = tmp_path / "mixed.jsonl"
    records_path.write_text(
        "{not json}\n" + json.dumps({"task_id": "ok", "answer": "7", "verification_sql": "SELECT 7"}) + "\n",
        encoding="utf-8",
    )
    run = subprocess.run(
        [sys.executable, str(SCRIPT), str(records_path), str(warehouse)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run.returncode == 1
    assert "UNREADABLE ROW" in run.stdout
    assert "rows=2 failures=1" in run.stdout
