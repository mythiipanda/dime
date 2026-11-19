import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.reconciliation_runner import run_benchmark
from evals.reconciliation_scorer import score_adversarial, score_task, score_two_path


def _two_path_task(task_id, answer):
    return {
        "task_id": task_id,
        "slice": "two-path",
        "question": "How many games did the Harbor City club win?",
        "guidelines": "Return the win total as a plain number.",
        "level": "easy",
        "answer": answer,
        "expected_paths": [
            {"name": "standings", "sql": "SELECT WINS FROM silver_standings"},
            {"name": "game_log", "sql": "SELECT COUNT(*) FROM silver_team_games"},
        ],
        "resolution_notes": "Both sources report the same total.",
    }


def _adversarial_task(task_id, answer):
    return {
        "task_id": task_id,
        "slice": "adversarial",
        "question": "How many games did the Portside club win?",
        "guidelines": "Return the win total as a plain number.",
        "level": "hard",
        "answer": answer,
    }


def test_agreeing_correct_paths_pass():
    assert score_two_path(["46", "46"], "46") == {
        "consistent": True,
        "correct": True,
        "passed": True,
    }


def test_disagreeing_paths_fail_consistency():
    assert score_two_path(["46", "36"], "46") == {
        "consistent": False,
        "correct": False,
        "passed": False,
    }


def test_close_paths_can_be_correct_but_inconsistent():
    assert score_two_path(["99.993", "100.005"], "100") == {
        "consistent": False,
        "correct": True,
        "passed": False,
    }


def test_agreeing_wrong_paths_fail_correctness():
    assert score_two_path(["36", "36"], "46") == {
        "consistent": True,
        "correct": False,
        "passed": False,
    }


def test_comma_formatted_numbers_agree():
    assert score_two_path(["2,143", "2143"], "2143") == {
        "consistent": True,
        "correct": True,
        "passed": True,
    }


def test_identical_names_pass():
    assert score_two_path(["Harbor City", "Harbor City"], "Harbor City") == {
        "consistent": True,
        "correct": True,
        "passed": True,
    }


def test_different_names_fail():
    assert score_two_path(["Harbor City", "Portside"], "Harbor City") == {
        "consistent": False,
        "correct": False,
        "passed": False,
    }


def test_number_and_text_pair_is_inconsistent():
    assert score_two_path(["46", "forty six"], "46") == {
        "consistent": False,
        "correct": False,
        "passed": False,
    }


def test_rel_tol_applies_to_both_checks():
    assert score_two_path(["100", "101"], "100", rel_tol=0.02) == {
        "consistent": True,
        "correct": True,
        "passed": True,
    }
    assert score_two_path(["100", "101"], "100") == {
        "consistent": False,
        "correct": False,
        "passed": False,
    }


def test_empty_paths_fail():
    assert score_two_path([], "46") == {
        "consistent": False,
        "correct": False,
        "passed": False,
    }


def test_adversarial_exact_match():
    assert score_adversarial("46", "46") is True


def test_adversarial_numeric_tolerance():
    assert score_adversarial("2143", "2,143") is True
    assert score_adversarial("46.0", "46") is True


def test_adversarial_wrong_number():
    assert score_adversarial("36", "46") is False


def test_adversarial_ignores_case_and_punctuation():
    assert score_adversarial("Harbor City!", "harbor city") is True


def test_adversarial_different_text():
    assert score_adversarial("Harbor City", "Portside") is False


def test_score_task_two_path_pass():
    task = _two_path_task("rec2p-001", "46")
    assert score_task(task, {"paths": ["46", "46"]}) == {
        "passed": True,
        "slice": "two-path",
        "detail": {"consistent": True, "correct": True},
    }


def test_score_task_two_path_disagreement_fails():
    task = _two_path_task("rec2p-001", "46")
    result = score_task(task, {"paths": ["46", "36"]})
    assert result["passed"] is False
    assert result["slice"] == "two-path"
    assert result["detail"]["consistent"] is False


def test_score_task_missing_paths_fails():
    task = _two_path_task("rec2p-001", "46")
    result = score_task(task, {})
    assert result["passed"] is False
    assert result["slice"] == "two-path"


def test_score_task_adversarial():
    task = _adversarial_task("reca-001", "46")
    assert score_task(task, {"answer": "46"}) == {
        "passed": True,
        "slice": "adversarial",
        "detail": {"matched": True},
    }
    failed = score_task(task, {"answer": "36"})
    assert failed == {
        "passed": False,
        "slice": "adversarial",
        "detail": {"matched": False},
    }


def _stub_model(task):
    if task["slice"] == "two-path":
        return {"paths": [task["answer"], task["answer"]]}
    return {"answer": task["answer"]}


def _disagreeing_stub(task):
    if task["slice"] == "two-path":
        return {"paths": [task["answer"], "not the same value at all"]}
    return {"answer": task["answer"]}


def _wrong_entity_stub(task):
    if task["slice"] == "two-path":
        return {"paths": ["32", "32"]}
    return {"answer": "Portside"}


def _garbled_stub(task):
    if task["slice"] == "two-path":
        return {"paths": ["@@@xx", "%%%yy"]}
    return {"answer": "@@@xx"}


def _mixed_rows():
    return [
        _two_path_task("rec2p-001", "46"),
        _two_path_task("rec2p-002", "36"),
        _adversarial_task("reca-001", "Harbor City"),
    ]


def test_perfect_stub_passes_everything():
    report = run_benchmark(_mixed_rows(), _stub_model)
    assert report["total"] == 3
    assert report["slices"]["two-path"] == {"total": 2, "passed": 2, "pass_rate": 1.0}
    assert report["slices"]["adversarial"] == {"total": 1, "passed": 1, "pass_rate": 1.0}
    assert report["failed"] == []


def test_disagreeing_stub_fails_only_two_path():
    report = run_benchmark(_mixed_rows(), _disagreeing_stub)
    assert report["total"] == 3
    assert report["slices"]["two-path"] == {"total": 2, "passed": 0, "pass_rate": 0.0}
    assert report["slices"]["adversarial"] == {"total": 1, "passed": 1, "pass_rate": 1.0}
    assert report["failed"] == ["rec2p-001", "rec2p-002"]


def test_wrong_entity_stub_is_consistent_but_wrong():
    report = run_benchmark(_mixed_rows(), _wrong_entity_stub)
    assert report["total"] == 3
    assert report["slices"]["two-path"] == {"total": 2, "passed": 0, "pass_rate": 0.0}
    assert report["slices"]["adversarial"] == {"total": 1, "passed": 0, "pass_rate": 0.0}
    assert report["failed"] == ["rec2p-001", "rec2p-002", "reca-001"]


def test_garbled_stub_fails_everything():
    report = run_benchmark(_mixed_rows(), _garbled_stub)
    assert report["total"] == 3
    assert report["slices"]["two-path"]["passed"] == 0
    assert report["slices"]["adversarial"]["passed"] == 0
    assert report["failed"] == ["rec2p-001", "rec2p-002", "reca-001"]


def test_empty_rows():
    assert run_benchmark([], _stub_model) == {"total": 0, "slices": {}, "failed": []}


_SHIPPED = Path(__file__).resolve().parent / "reconciliation_stress.jsonl"


def _load_shipped():
    with open(_SHIPPED, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _full_perfect_stub(task):
    if task["slice"] == "two-path":
        return {"paths": [task["answer"], task["answer"]]}
    return {"answer": task["answer"]}


def _full_wrong_entity_stub(task):
    if task["slice"] == "two-path":
        return {"paths": [task["answer"], task["answer"]]}
    return {"answer": "Wrongville"}


def _full_disagreeing_stub(task):
    if task["slice"] == "two-path":
        return {"paths": ["3", "9000001"]}
    return {"answer": task["answer"]}


def test_full_file_perfect_stub_scores_150():
    rows = _load_shipped()
    assert len(rows) == 150
    report = run_benchmark(rows, _full_perfect_stub)
    assert report["total"] == 150
    assert report["slices"]["two-path"] == {"total": 100, "passed": 100, "pass_rate": 1.0}
    assert report["slices"]["adversarial"] == {"total": 50, "passed": 50, "pass_rate": 1.0}
    assert report["failed"] == []


def test_full_file_wrong_entity_fails_only_adversarial():
    rows = _load_shipped()
    assert len(rows) == 150
    report = run_benchmark(rows, _full_wrong_entity_stub)
    assert report["total"] == 150
    assert report["slices"]["two-path"] == {"total": 100, "passed": 100, "pass_rate": 1.0}
    assert report["slices"]["adversarial"]["total"] == 50
    assert report["slices"]["adversarial"]["passed"] == 0
    assert report["slices"]["adversarial"]["pass_rate"] == 0.0


def test_full_file_disagreeing_paths_fails_only_two_path():
    rows = _load_shipped()
    assert len(rows) == 150
    report = run_benchmark(rows, _full_disagreeing_stub)
    assert report["total"] == 150
    assert report["slices"]["two-path"]["total"] == 100
    assert report["slices"]["two-path"]["passed"] == 0
    assert report["slices"]["two-path"]["pass_rate"] == 0.0
    assert report["slices"]["adversarial"] == {"total": 50, "passed": 50, "pass_rate": 1.0}
