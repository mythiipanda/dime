import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.dabstep import LEVELS, SCHEMA_FIELDS, template_row, validate_row


def valid_row():
    return {
        "task_id": "dabstep-001",
        "question": "Which club scored the most points in the 2023-24 season?",
        "guidelines": "Use only the warehouse games table.",
        "level": "easy",
        "answer": "Harbor Seals",
        "tools_required": ["query_warehouse"],
        "pretraining_note": "requires warehouse aggregation over the full season",
    }


def test_schema_fields_contains_required():
    for field in ("task_id", "question", "guidelines", "level", "answer"):
        assert field in SCHEMA_FIELDS


def test_levels_exact():
    assert LEVELS == ("easy", "hard")


def test_validate_row_valid():
    assert validate_row(valid_row()) == []


def test_validate_row_missing_answer():
    row = valid_row()
    del row["answer"]
    errors = validate_row(row)
    assert errors != []
    assert any("answer" in e for e in errors)


def test_validate_row_bad_level():
    row = valid_row()
    row["level"] = "medium"
    errors = validate_row(row)
    assert errors != []
    assert any("level" in e for e in errors)


def test_validate_row_empty_tools_required():
    row = valid_row()
    row["tools_required"] = []
    errors = validate_row(row)
    assert errors != []
    assert any("tools_required" in e for e in errors)


def test_validate_row_empty_pretraining_note():
    row = valid_row()
    row["pretraining_note"] = ""
    errors = validate_row(row)
    assert errors != []
    assert any("pretraining_note" in e for e in errors)


def test_template_row_has_schema_fields():
    row = template_row()
    for field in SCHEMA_FIELDS:
        assert field in row


def test_template_row_has_toolqa_fields():
    row = template_row()
    assert "tools_required" in row
    assert "pretraining_note" in row


def test_blank_task_id_is_rejected():
    row = valid_row()
    row["task_id"] = "   "
    errors = validate_row(row)
    assert errors != []
    assert any("task_id" in e for e in errors)


def test_missing_guidelines_is_rejected():
    row = valid_row()
    del row["guidelines"]
    errors = validate_row(row)
    assert errors != []
    assert any("guidelines" in e for e in errors)


def test_authoring_template_rows_all_validate():
    path = Path(__file__).resolve().parent.parent / "evals" / "dabstep_authoring_template.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert len(rows) == 3
    task_ids = [row["task_id"] for row in rows]
    assert len(set(task_ids)) == len(task_ids)
    for row in rows:
        assert validate_row(row) == []
