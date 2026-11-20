import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.evals.multihop_runner import load_questions, run_benchmark

REPO = Path(__file__).resolve().parent.parent
JSONL = REPO / "evals" / "multihop_nba.jsonl"

EXPECTED_IDS = ["mnba-easy-%03d" % i for i in range(1, 76)] + ["mnba-hard-%03d" % i for i in range(1, 76)]


@pytest.fixture(scope="module")
def rows():
    return load_questions(str(JSONL))


def test_row_count_and_task_ids(rows):
    assert len(rows) == 150
    assert [r["task_id"] for r in rows] == EXPECTED_IDS


def test_level_split(rows):
    levels = [r["level"] for r in rows]
    assert levels.count("easy") == 75
    assert levels.count("hard") == 75
    assert all(r["level"] == "easy" for r in rows[:75])
    assert all(r["level"] == "hard" for r in rows[75:])


def test_answer_types(rows):
    for r in rows:
        assert isinstance(r["answer"], (int, float, str)) and not isinstance(r["answer"], bool), r["task_id"]


def test_required_keys_and_nonempty_text(rows):
    for r in rows:
        assert set(("task_id", "question", "guidelines", "level", "answer")) <= set(r.keys()), r["task_id"]
        assert len(r["question"].strip()) > 30, r["task_id"]
        assert len(r["guidelines"].strip()) >= 20, r["task_id"]


def test_no_duplicate_questions(rows):
    questions = [r["question"] for r in rows]
    assert len(set(questions)) == len(questions)


def test_no_duplicate_task_ids(rows):
    task_ids = [r["task_id"] for r in rows]
    assert len(set(task_ids)) == len(task_ids)


def test_guidelines_do_not_leak_string_answers(rows):
    for r in rows:
        if isinstance(r["answer"], str):
            assert r["answer"] not in r["guidelines"], r["task_id"]


def test_gold_solver_scores_perfect_over_full_suite(rows):
    answers = {(r["question"], r["guidelines"]): r["answer"] for r in rows}

    def solver(question, guidelines):
        return answers[(question, guidelines)]

    out = run_benchmark(solver, rows, hard_attempts=2)
    assert out["n_easy"] == 75
    assert out["n_hard"] == 75
    assert out["easy_accuracy"] == 1.0
    assert out["hard_pass2_accuracy"] == 1.0
    assert all(r["passed"] for r in out["results"])
