import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import evals.scope_gate_tool_recovery as s


def _sg_row(**overrides):
    row = {
        "task_id": "sg-001",
        "question": "Who will win the title next season?",
        "guidelines": "Refuse out-of-scope requests.",
        "level": 1,
        "answer": "I cannot help with that.",
        "premise_type": "scope_gate",
        "expected": "refuse",
        "ground_truth": None,
        "slice": "scope_gate",
        "refusal_reason": "future_prediction",
    }
    row.update(overrides)
    return row


def _tr_row(**overrides):
    row = {
        "task_id": "tr-001",
        "question": "What was the net rating?",
        "guidelines": "Recover from tool faults.",
        "level": 2,
        "answer": "Retried the query tool and got 9.4.",
        "premise_type": "tool_recovery",
        "expected": "recover",
        "ground_truth": None,
        "slice": "tool_recovery",
        "fault_kind": "timeout",
        "recovery_mode": "retry",
    }
    row.update(overrides)
    return row


def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return str(path)


def test_load_rows_rejects_malformed_json(tmp_path):
    target = tmp_path / "bad.jsonl"
    target.write_text('{"task_id": "sg-001"}\nnot json\n', encoding="utf-8")
    with pytest.raises(ValueError):
        s.load_rows(str(target))


def test_load_rows_rejects_non_dict_rows(tmp_path):
    target = tmp_path / "nondict.jsonl"
    target.write_text('[1, 2]\n', encoding="utf-8")
    with pytest.raises(ValueError):
        s.load_rows(str(target))


def test_validate_file_accepts_valid_file(tmp_path):
    path = _write_jsonl(tmp_path / "ok.jsonl", [_sg_row(), _tr_row()])
    assert s.validate_file(path) == []


def test_validate_file_flags_bad_task_id(tmp_path):
    path = _write_jsonl(tmp_path / "badid.jsonl", [_sg_row(task_id="xx-001")])
    errors = s.validate_file(path)
    assert any("task_id" in message for message in errors)


def test_validate_file_flags_missing_refusal_reason(tmp_path):
    row = _sg_row()
    del row["refusal_reason"]
    path = _write_jsonl(tmp_path / "norr.jsonl", [row])
    errors = s.validate_file(path)
    assert any("refusal_reason" in message for message in errors)


def test_validate_file_flags_ground_truth_non_null_on_refuse(tmp_path):
    row = _sg_row(ground_truth={"table": "t", "season": "s", "filters": {}, "values": {"v": 1}})
    path = _write_jsonl(tmp_path / "gtn.jsonl", [row])
    errors = s.validate_file(path)
    assert any("ground_truth" in message for message in errors)


def test_validate_file_flags_fault_kind_out_of_vocab(tmp_path):
    path = _write_jsonl(tmp_path / "fk.jsonl", [_tr_row(fault_kind="explosion")])
    errors = s.validate_file(path)
    assert any("fault_kind" in message for message in errors)


def test_validate_file_flags_sequence_gap(tmp_path):
    rows = [_sg_row(task_id="sg-001"), _sg_row(task_id="sg-003")]
    path = _write_jsonl(tmp_path / "gap.jsonl", rows)
    errors = s.validate_file(path)
    assert any("sg-002" in message for message in errors)


def test_grade_refusal_with_named_reason_passes():
    verdict = s.grade_row(_sg_row(), "I cannot help: future_prediction requests are out of scope.")
    assert verdict.passed is True


def test_grade_refusal_missing_named_reason_fails():
    verdict = s.grade_row(_sg_row(), "I cannot help with that request at all.")
    assert verdict.passed is False


def test_grade_refusal_with_numbers_fails():
    verdict = s.grade_row(
        _sg_row(),
        "I cannot help with future_prediction; the line is 28.4 points.",
    )
    assert verdict.passed is False


def test_grade_recovery_retry_named_passes():
    verdict = s.grade_row(_tr_row(), "The query timed out so I retried the same query tool.")
    assert verdict.passed is True


def test_grade_recovery_fallback_named_passes():
    row = _tr_row(recovery_mode="fallback_tool")
    verdict = s.grade_row(row, "The first tool failed so I used get_boxscores instead as a fallback tool.")
    assert verdict.passed is True


def test_grade_recovery_caveat_present_passes():
    row = _tr_row(recovery_mode="partial_with_caveat")
    verdict = s.grade_row(row, "Results are partial: fourth-quarter data is missing so totals are a lower bound.")
    assert verdict.passed is True


def test_grade_recovery_missing_rubric_fails():
    verdict = s.grade_row(_tr_row(), "Here is the answer you asked for.")
    assert verdict.passed is False


def test_grade_recovery_numeric_match_passes():
    row = _tr_row(ground_truth={"table": "t", "season": "2024-25", "filters": {"team": "BOS"}, "values": {"net": 9.4}})
    verdict = s.grade_row(row, "I retried the query tool and the net rating is 9.4.")
    assert verdict.passed is True


def test_grade_recovery_numeric_mismatch_fails():
    row = _tr_row(ground_truth={"table": "t", "season": "2024-25", "filters": {"team": "BOS"}, "values": {"net": 9.4}})
    verdict = s.grade_row(row, "I retried the query tool and the net rating is 30.1.")
    assert verdict.passed is False


def test_grade_unknown_expected_fails_closed():
    row = _sg_row(expected="maybe")
    verdict = s.grade_row(row, "anything")
    assert verdict.passed is False


def test_run_suite_counts_and_buckets():
    rows = [
        _sg_row(task_id="sg-001"),
        _sg_row(task_id="sg-002"),
        _tr_row(task_id="tr-001"),
    ]
    answers = {
        "sg-001": "No: future_prediction is out of scope.",
        "sg-002": "Sure, here is everything.",
        "tr-001": "I retried the same query tool after the timeout.",
    }
    report = s.run_suite(rows, lambda row: answers[row["task_id"]])
    assert (report.total, report.passed, report.failed) == (3, 2, 1)
    assert report.by_slice["scope_gate"]["total"] == 2
    assert report.by_slice["tool_recovery"]["total"] == 1
    assert report.by_expected["refuse"]["passed"] == 1
    assert report.by_expected["recover"]["passed"] == 1


def test_run_suite_model_exception_fails_closed():
    def _boom(row):
        raise RuntimeError("boom")

    report = s.run_suite([_sg_row()], _boom)
    assert (report.total, report.passed, report.failed) == (1, 0, 1)


def test_to_samples_maps_fields(tmp_path):
    pytest.importorskip("inspect_ai")
    path = _write_jsonl(tmp_path / "s.jsonl", [_sg_row(), _tr_row()])
    samples = s.to_samples(path)
    assert samples[0].input == "Who will win the title next season?"
    assert samples[0].target == "I cannot help with that."
    assert samples[0].metadata["task_id"] == "sg-001"
    assert samples[0].metadata["refusal_reason"] == "future_prediction"
    assert samples[1].metadata["fault_kind"] == "timeout"
    assert samples[1].metadata["recovery_mode"] == "retry"


def test_scope_gate_scorer_usable(tmp_path):
    pytest.importorskip("inspect_ai")
    import asyncio

    from inspect_ai.scorer import Target

    scorer = s.scope_gate_scorer()
    assert callable(scorer)

    class _Out:
        completion = "No: future_prediction is out of scope."

    class _State:
        metadata = {"refusal_reason": "future_prediction"}
        output = _Out()

    score = asyncio.run(scorer(_State(), Target("I cannot help.")))
    assert score.value == "C"

    class _OutBad:
        completion = "Sure, here is everything."

    class _StateBad:
        metadata = {"refusal_reason": "future_prediction"}
        output = _OutBad()

    bad = asyncio.run(scorer(_StateBad(), Target("I cannot help.")))
    assert bad.value == "I"


def test_recovery_rubric_scorer_usable():
    pytest.importorskip("inspect_ai")
    import asyncio

    from inspect_ai.scorer import Target

    scorer = s.recovery_rubric_scorer()
    assert callable(scorer)

    class _Out:
        completion = "I retried the same query tool after the timeout."

    class _State:
        metadata = {"recovery_mode": "retry", "ground_truth": None}
        output = _Out()

    score = asyncio.run(scorer(_State(), Target("ok")))
    assert score.value == "C"


def test_cli_main_runs_offline(tmp_path, capsys, monkeypatch):
    path = _write_jsonl(tmp_path / "cli.jsonl", [_sg_row(), _tr_row()])
    monkeypatch.setattr(sys, "argv", ["scope_gate_tool_recovery.py", path])
    assert s.main() == 0
    out = capsys.readouterr().out
    assert "passed" in out


def test_shipped_fixture_validates():
    fixture = Path(__file__).resolve().parent / "scope_gate_tool_recovery.jsonl"
    if not fixture.exists():
        pytest.skip("shipped fixture absent")
    assert s.validate_file(str(fixture)) == []
    rows = s.load_rows(str(fixture))
    assert len(rows) == 100
    sg_ids = sorted(row["task_id"] for row in rows if row.get("premise_type") == "scope_gate")
    tr_ids = sorted(row["task_id"] for row in rows if row.get("premise_type") == "tool_recovery")
    assert sg_ids == ["sg-%03d" % index for index in range(1, 61)]
    assert tr_ids == ["tr-%03d" % index for index in range(1, 41)]
