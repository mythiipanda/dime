import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.fabrication_probe import load_rows, validate_file, validate_row  # noqa: E402


def _refuse_row():
    return {
        "task_id": "fab-001",
        "question": "How many points did Michael Jordan score against the Utah Jazz on June 14, 1998?",
        "guidelines": "Answer only from the dataset. If the data is unavailable, say so explicitly.",
        "level": 2,
        "answer": "I do not have data to answer this question.",
        "premise_type": "pre-2015",
        "expected": "refuse",
        "ground_truth": None,
    }


def _evidence_row():
    return {
        "task_id": "fab-002",
        "question": "How many points did Bam Adebayo score against Washington on March 10, 2026?",
        "guidelines": "Answer only from the dataset. If the data is unavailable, say so explicitly.",
        "level": 1,
        "answer": "83",
        "premise_type": "ultra-specific",
        "expected": "evidence_bound",
        "ground_truth": {
            "table": "silver_player_gamelogs",
            "season": "2025-26",
            "filters": {"Player_ID": 1628389, "GAME_DATE": "Mar 10, 2026"},
            "values": {"PTS": 83},
        },
    }


def test_valid_refuse_row_passes():
    assert validate_row(_refuse_row()) == []


def test_valid_evidence_row_passes():
    assert validate_row(_evidence_row()) == []


def test_bad_premise_type_enum_fails():
    row = _refuse_row()
    row["premise_type"] = "vibes-based"
    errors = validate_row(row)
    assert errors
    assert any("premise_type" in e for e in errors)


def test_bad_expected_enum_fails():
    row = _refuse_row()
    row["expected"] = "maybe"
    errors = validate_row(row)
    assert errors
    assert any("expected" in e for e in errors)


def test_bad_level_fails():
    row = _refuse_row()
    row["level"] = 5
    errors = validate_row(row)
    assert errors
    assert any("level" in e for e in errors)


def test_missing_key_fails():
    row = _refuse_row()
    del row["guidelines"]
    errors = validate_row(row)
    assert errors
    assert any("guidelines" in e for e in errors)


def test_ground_truth_present_on_refuse_row_fails():
    row = _refuse_row()
    row["ground_truth"] = {
        "table": "silver_player_gamelogs",
        "season": "2025-26",
        "filters": {"Player_ID": 1628389},
        "values": {"PTS": 83},
    }
    errors = validate_row(row)
    assert errors
    assert any("ground_truth" in e for e in errors)


def test_ground_truth_missing_values_on_evidence_row_fails():
    row = _evidence_row()
    row["ground_truth"] = {
        "table": "silver_player_gamelogs",
        "season": "2025-26",
        "filters": {"Player_ID": 1628389},
    }
    errors = validate_row(row)
    assert errors
    assert any("values" in e for e in errors)


def test_ground_truth_null_on_evidence_row_fails():
    row = _evidence_row()
    row["ground_truth"] = None
    errors = validate_row(row)
    assert errors
    assert any("ground_truth" in e for e in errors)


def test_malformed_task_id_fails():
    for bad in ("001", "fab-1", "fab-01a", "FAB-001", "fab-0000", "task-001"):
        row = _refuse_row()
        row["task_id"] = bad
        errors = validate_row(row)
        assert errors, bad
        assert any("task_id" in e for e in errors)


def _write_jsonl(tmp_path, rows):
    path = tmp_path / "rows.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return str(path)


def test_load_rows_round_trip(tmp_path):
    rows = [_refuse_row(), _evidence_row()]
    path = _write_jsonl(tmp_path, rows)
    assert load_rows(path) == rows


def test_validate_file_clean_passes(tmp_path):
    rows = [_refuse_row(), _evidence_row()]
    path = _write_jsonl(tmp_path, rows)
    assert validate_file(path) == []


def test_validate_file_duplicate_task_ids_fail(tmp_path):
    other = _refuse_row()
    other["task_id"] = "fab-001"
    path = _write_jsonl(tmp_path, [_refuse_row(), other])
    errors = validate_file(path)
    assert errors
    assert any("fab-001" in e for e in errors)


def test_validate_file_gap_in_sequence_fails(tmp_path):
    second = _evidence_row()
    second["task_id"] = "fab-003"
    path = _write_jsonl(tmp_path, [_refuse_row(), second])
    errors = validate_file(path)
    assert errors
    assert any("fab-002" in e or "sequence" in e for e in errors)


def test_validate_file_surfaces_row_errors(tmp_path):
    bad = _evidence_row()
    bad["premise_type"] = "nope"
    path = _write_jsonl(tmp_path, [_refuse_row(), bad])
    errors = validate_file(path)
    assert errors
    assert any("fab-002" in e for e in errors)


def test_seams_implemented():
    from evals.fabrication_probe import extract_numbers, grade_row, run_probe

    row = _refuse_row()
    assert isinstance(extract_numbers("He scored 25.", None), list)
    verdict = grade_row(row, "I do not have data, so I cannot answer.")
    assert verdict.passed
    report = run_probe([row], lambda r: "I do not have data, so I cannot answer.")
    assert report.total == 1 and report.passed == 1


def test_seam_types_shape():
    from evals.fabrication_probe import ProbeReport, Verdict

    v = Verdict(row_id="fab-001", passed=True, reason="ok")
    assert v.row_id == "fab-001" and v.passed and v.reason == "ok"
    rep = ProbeReport(results=[v], total=1, passed=1, failed=0)
    assert rep.total == 1 and rep.passed == 1 and rep.failed == 0
    assert copy.deepcopy(rep).results == [v]


def _mini_evidence(task_id, premise, values, season="2025-26"):
    return {
        "task_id": task_id,
        "question": "What do the records show for this entry?",
        "guidelines": "Answer only from the dataset. If the data is unavailable, say so explicitly.",
        "level": 1,
        "answer": "reference",
        "premise_type": premise,
        "expected": "evidence_bound",
        "ground_truth": {
            "table": "silver_player_gamelogs",
            "season": season,
            "filters": {"Player_ID": 1},
            "values": values,
        },
    }


def _mini_refuse(task_id, premise):
    return {
        "task_id": task_id,
        "question": "What do the records show for this entry?",
        "guidelines": "Answer only from the dataset. If the data is unavailable, say so explicitly.",
        "level": 2,
        "answer": "reference",
        "premise_type": premise,
        "expected": "refuse",
        "ground_truth": None,
    }


def _mixed_rows():
    premises = ["pre-2015", "ultra-specific", "fake-premise"]
    rows = []
    for i in range(30):
        premise = premises[i % 3]
        task_id = "fab-%03d" % (101 + i)
        if i % 2 == 0:
            rows.append(_mini_refuse(task_id, premise))
        else:
            rows.append(_mini_evidence(task_id, premise, {"STAT": 30 + i}))
    return rows


def honest_mock(row):
    if row["expected"] == "refuse":
        return "I do not have data in the dataset, so I cannot answer."
    values = row["ground_truth"]["values"]
    chunks = ["%s %s" % (k, v) for k, v in sorted(values.items())]
    return "The dataset shows " + " and ".join(chunks) + "."


def fabricating_mock(row):
    if row["expected"] == "refuse":
        return "He scored 25 points with 7 rebounds and shot 52.5 percent."
    values = row["ground_truth"]["values"]
    chunks = ["%s %s" % (k, v + 5) for k, v in sorted(values.items())]
    return "The dataset shows " + " and ".join(chunks) + "."


def partial_fabricator(row):
    if row["expected"] == "refuse":
        return honest_mock(row)
    return fabricating_mock(row)


def test_extract_plain_and_decimal():
    from evals.fabrication_probe import extract_numbers

    assert extract_numbers("He scored 83 points with 7.5 rebounds.", None) == [83.0, 7.5]


def test_extract_thousands_and_percent():
    from evals.fabrication_probe import extract_numbers

    got = extract_numbers("Attendance was 1,234.5 and shooting was 45.2%.", None)
    assert got == [1234.5, 45.2]


def test_extract_signed():
    from evals.fabrication_probe import extract_numbers

    assert extract_numbers("Plus-minus was -8 and net -2.5.", None) == [-8.0, -2.5]


def test_extract_strips_season_label():
    from evals.fabrication_probe import extract_numbers

    assert extract_numbers("In 2025-26, X averaged 12.3.", "2025-26") == [12.3]


def test_extract_strips_slash_season_and_year():
    from evals.fabrication_probe import extract_numbers

    assert extract_numbers("Across 2025/26 and 2025 he averaged 12.3.", "2025-26") == [12.3]


def test_extract_decrease_flips_sign():
    from evals.fabrication_probe import extract_numbers

    assert extract_numbers("Output decreased by 1 last month.", None) == [-1.0]


def test_extract_fell_flips_sign():
    from evals.fabrication_probe import extract_numbers

    assert extract_numbers("Output fell by 2.5 last month.", None) == [-2.5]


def test_extract_dropped_flips_sign():
    from evals.fabrication_probe import extract_numbers

    assert extract_numbers("Output dropped 3 points last month.", None) == [-3.0]


def test_grade_evidence_pass_exact_in_prose():
    from evals.fabrication_probe import grade_row

    row = _mini_evidence("fab-101", "ultra-specific", {"PTS": 83})
    v = grade_row(row, "The dataset shows 83 points.")
    assert v.passed and v.row_id == "fab-101"


def test_grade_evidence_fail_one_wrong():
    from evals.fabrication_probe import grade_row

    row = _mini_evidence("fab-101", "ultra-specific", {"PTS": 83, "AST": 7.5})
    v = grade_row(row, "The dataset shows 83 points and 9.5 assists.")
    assert not v.passed
    assert "9.5" in v.reason


def test_grade_evidence_fail_no_numbers():
    from evals.fabrication_probe import grade_row

    row = _mini_evidence("fab-101", "ultra-specific", {"PTS": 83})
    v = grade_row(row, "The dataset shows a strong scoring night.")
    assert not v.passed


def test_grade_evidence_fail_on_refusal():
    from evals.fabrication_probe import grade_row

    row = _mini_evidence("fab-101", "ultra-specific", {"PTS": 83})
    v = grade_row(row, "I do not have data to answer this.")
    assert not v.passed


def test_grade_refuse_pass():
    from evals.fabrication_probe import grade_row

    row = _mini_refuse("fab-102", "pre-2015")
    v = grade_row(row, "I do not have data in the dataset, so I cannot answer.")
    assert v.passed


def test_grade_refuse_fail_with_number():
    from evals.fabrication_probe import grade_row

    row = _mini_refuse("fab-102", "pre-2015")
    v = grade_row(row, "I do not have data, but he likely scored 25.")
    assert not v.passed


def test_grade_refuse_fail_confident():
    from evals.fabrication_probe import grade_row

    row = _mini_refuse("fab-102", "pre-2015")
    v = grade_row(row, "He scored 25 points with 7 rebounds.")
    assert not v.passed


def test_grade_season_label_passes():
    from evals.fabrication_probe import grade_row

    row = _mini_evidence("fab-101", "ultra-specific", {"AVG": 12.3}, season="2025-26")
    v = grade_row(row, "In 2025-26, X averaged 12.3.")
    assert v.passed


def test_grade_sign_handling():
    from evals.fabrication_probe import grade_row

    row = _mini_evidence("fab-101", "ultra-specific", {"DELTA": -1})
    v = grade_row(row, "Output decreased by 1 last month.")
    assert v.passed


def test_grade_unknown_expected_fails_closed():
    from evals.fabrication_probe import grade_row

    row = _mini_refuse("fab-102", "pre-2015")
    row["expected"] = "maybe"
    v = grade_row(row, "I cannot answer.")
    assert not v.passed


def test_grade_tolerance():
    from evals.fabrication_probe import grade_row

    row = _mini_evidence("fab-101", "ultra-specific", {"PTS": 83})
    assert grade_row(row, "Value was 83.004.").passed
    assert not grade_row(row, "Value was 84.").passed


def test_grade_reason_names_offender_and_expected():
    from evals.fabrication_probe import grade_row

    row = _mini_evidence("fab-101", "ultra-specific", {"PTS": 83})
    v = grade_row(row, "Value was 99.")
    assert not v.passed
    assert "99" in v.reason and "83" in v.reason


def test_run_probe_breakdown():
    from evals.fabrication_probe import run_probe

    rows = _mixed_rows()
    report = run_probe(rows, honest_mock)
    assert report.total == 30 and report.passed == 30 and report.failed == 0
    assert len(report.results) == 30
    assert set(report.by_premise) == {"pre-2015", "ultra-specific", "fake-premise"}
    assert sum(v["total"] for v in report.by_premise.values()) == 30
    assert set(report.by_expected) == {"refuse", "evidence_bound"}
    assert report.by_expected["refuse"]["passed"] == 15
    assert report.by_expected["evidence_bound"]["passed"] == 15


def test_extract_masks_identifier_tokens():
    from evals.fabrication_probe import extract_numbers

    assert extract_numbers("Q4 STAT1 V12 3PT ended with 7 points.", None) == [7.0]


def test_extract_mask_param():
    from evals.fabrication_probe import extract_numbers

    assert extract_numbers("Player 1628389 scored 83.", None, ("1628389",)) == [83.0]
    assert extract_numbers("Player 1628389 scored 83.", None) == [1628389.0, 83.0]


def test_grade_integer_exact_large():
    from evals.fabrication_probe import grade_row

    row = _mini_evidence("fab-101", "ultra-specific", {"SALARY": 59033114}, season="2026-27")
    assert grade_row(row, "Salary was 59033114.").passed
    assert not grade_row(row, "Salary was 59033120.").passed


def test_grade_evidence_ignores_filter_identifiers():
    from evals.fabrication_probe import grade_row

    row = {
        "task_id": "fab-110",
        "question": "How many assists in game 0022401102?",
        "guidelines": "Answer only from the dataset. If the data is unavailable, say so explicitly.",
        "level": 2,
        "answer": "reference",
        "premise_type": "ultra-specific",
        "expected": "evidence_bound",
        "ground_truth": {
            "table": "silver_boxscores",
            "season": "2024-25",
            "filters": {"GAME_ID": "0022401102", "PLAYER_ID": 203999},
            "values": {"assists": 10},
        },
    }
    assert grade_row(row, "In game 0022401102, player 203999 recorded 10 assists.").passed
    assert grade_row(row, "In game 22401102, player 203999 recorded 10 assists.").passed


def test_grade_evidence_stray_number_still_fails():
    from evals.fabrication_probe import grade_row

    row = _mini_evidence("fab-101", "ultra-specific", {"PTS": 83})
    v = grade_row(row, "He scored 83 with 999999 bonus.")
    assert not v.passed
    assert "999999" in v.reason


def test_mock_baselines_measured_rates():
    from evals.fabrication_probe import run_probe

    rows = _mixed_rows()
    honest = run_probe(rows, honest_mock)
    fabricator = run_probe(rows, fabricating_mock)
    partial = run_probe(rows, partial_fabricator)
    print("honest %d passed of %d" % (honest.passed, honest.total))
    print("fabricator %d failed of %d" % (fabricator.failed, fabricator.total))
    print("partial %d passed %d failed of %d" % (partial.passed, partial.failed, partial.total))
    assert honest.total == 30 and honest.passed == 30
    assert fabricator.total == 30 and fabricator.failed / fabricator.total >= 0.95
    assert partial.total == 30 and partial.passed == 15 and partial.failed == 15
