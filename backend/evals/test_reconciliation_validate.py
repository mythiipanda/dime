import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.reconciliation_validate import validate_file, validate_row

SHIPPED = Path(__file__).resolve().parent / "reconciliation_stress.jsonl"


def _good_two_path():
    return {
        "task_id": "rec2p-001",
        "slice": "two-path",
        "question": "How many games did the Harbor City club win?",
        "guidelines": "Give the total as a plain number.",
        "level": "easy",
        "answer": "46",
        "expected_paths": [
            {"name": "standings", "sql": "SELECT WINS FROM silver_standings"},
            {"name": "game_log", "sql": "SELECT COUNT(*) FROM silver_team_games"},
        ],
        "resolution_notes": "Both sources report 46.",
    }


def test_good_two_path_row_has_no_problems():
    assert validate_row(_good_two_path()) == []


def test_bad_task_id_format():
    row = _good_two_path()
    row["task_id"] = "task-1"
    assert validate_row(row) == [
        "task_id must look like rec2p-NNN or reca-NNN",
        "task_id prefix must match slice",
    ]


def test_adversarial_id_format_accepted():
    row = _good_two_path()
    row["task_id"] = "reca-007"
    row["slice"] = "adversarial"
    del row["expected_paths"]
    assert validate_row(row) == []


def test_bad_slice_rejected():
    row = _good_two_path()
    row["slice"] = "single-path"
    assert validate_row(row) == ["slice must be two-path or adversarial"]


def test_bad_level_rejected():
    row = _good_two_path()
    row["level"] = "medium"
    assert validate_row(row) == ["level must be easy or hard"]


def test_empty_answer_rejected():
    row = _good_two_path()
    row["answer"] = ""
    assert validate_row(row) == ["answer must be a non-empty string"]


def test_whitespace_only_answer_rejected():
    row = _good_two_path()
    row["answer"] = "   "
    assert validate_row(row) == ["answer must be a non-empty string"]


def test_task_id_prefix_must_match_slice():
    row = _good_two_path()
    row["task_id"] = "reca-001"
    assert validate_row(row) == ["task_id prefix must match slice"]


def test_single_expected_path_rejected():
    row = _good_two_path()
    row["expected_paths"] = [{"name": "only", "sql": "SELECT 1"}]
    assert validate_row(row) == ["expected_paths needs at least 2 entries"]


def test_path_entry_without_sql_rejected():
    row = _good_two_path()
    row["expected_paths"] = [
        {"name": "a", "sql": "SELECT 1"},
        {"name": "b"},
    ]
    assert validate_row(row) == ["expected_paths entry has empty sql"]


def test_shipped_file_validates_clean():
    summary = validate_file(str(SHIPPED))
    assert summary["total"] == 150
    assert summary["invalid"] == 0
    assert summary["errors"] == []
