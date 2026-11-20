import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scope_gate_tool_recovery as recovery


def _row(premise, expected):
    refusing = expected == "refuse"
    return {
        "task_id": "sg-001" if premise == "scope_gate" else "tr-001",
        "question": "question",
        "guidelines": "guidelines",
        "level": 1,
        "answer": "answer",
        "premise_type": premise,
        "expected": expected,
        "ground_truth": None if refusing else {
            "table": "silver_stats",
            "season": "2024-25",
            "filters": {},
            "values": {"points": 20},
        },
        "slice": premise,
        "refusal_reason": "out_of_scope_capability" if refusing else None,
        "fault_kind": None if refusing else "timeout",
        "recovery_mode": None if refusing else "retry",
    }


def test_validate_refusal_row():
    assert recovery.validate_row(_row("scope_gate", "refuse")) == []


def test_validate_recovery_row():
    assert recovery.validate_row(_row("tool_recovery", "recover")) == []


def test_validate_row_preserves_early_error_order():
    row = _row("scope_gate", "refuse")
    row.update(task_id="sg-000", level=True, premise_type="other", expected=None)
    assert recovery.validate_row(row) == [
        "sg task_id number must be in range 001..060",
        "level must be one of 1, 2, 3",
        "premise_type must be one of scope_gate, tool_recovery",
        "expected must be one of refuse, recover",
    ]
