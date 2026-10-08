import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.evals.multihop_runner import load_questions, run_benchmark


def _easy(question="Who won?", answer="Lakers", task_id="e1"):
    return {
        "task_id": task_id,
        "question": question,
        "guidelines": "g",
        "level": "easy",
        "answer": answer,
    }


def _hard(question="How many?", answer="27.5", task_id="h1"):
    return {
        "task_id": task_id,
        "question": question,
        "guidelines": "g",
        "level": "hard",
        "answer": answer,
    }


def _gold_solver(questions):
    answers = {(q["question"], q["guidelines"]): q["answer"] for q in questions}

    def solver(question, guidelines):
        return answers[(question, guidelines)]

    return solver


def test_solver_receives_question_text_and_guidelines_only():
    questions = [_easy(question="Who won?", answer="Lakers")]
    seen = []

    def solver(question, guidelines):
        seen.append((question, guidelines))
        return "Lakers"

    run_benchmark(solver, questions)
    assert seen == [("Who won?", "g")]


def test_solver_never_sees_answer():
    questions = [_easy(question="Who won?", answer="Lakers")]

    def solver(question, guidelines):
        assert "Lakers" not in question
        return "Lakers"

    out = run_benchmark(solver, questions)
    assert out["easy_accuracy"] == 1.0


def test_perfect_solver_scores_full_accuracy():
    questions = [_easy(), _hard()]
    out = run_benchmark(_gold_solver(questions), questions)
    assert out["easy_accuracy"] == 1.0
    assert out["hard_pass2_accuracy"] == 1.0
    assert out["n_easy"] == 1
    assert out["n_hard"] == 1
    assert out["results"] == [
        {"task_id": "e1", "level": "easy", "attempts": 1, "scores": [1.0], "errors": [], "passed": True},
        {"task_id": "h1", "level": "hard", "attempts": 3, "scores": [1.0, 1.0, 1.0], "errors": [], "passed": True},
    ]


def test_always_wrong_solver_scores_zero():
    questions = [_easy(), _hard()]

    def solver(question, guidelines):
        return "definitely not the answer xyz"

    out = run_benchmark(solver, questions)
    assert out["easy_accuracy"] == 0.0
    assert out["hard_pass2_accuracy"] == 0.0
    assert out["results"][0]["passed"] is False
    assert out["results"][1]["passed"] is False
    assert out["results"][1]["scores"] == [0.0, 0.0, 0.0]
    assert out["results"][1]["errors"] == []


def test_flaky_hard_solver_fails_pass_squared():
    questions = [_hard()]
    calls = {"n": 0}
    answers = _gold_solver(questions)

    def solver(question, guidelines):
        calls["n"] += 1
        if calls["n"] == 1:
            return answers(question, guidelines)
        return "definitely not the answer xyz"

    out = run_benchmark(solver, questions, hard_attempts=2)
    assert out["results"][0]["scores"] == [1.0, 0.0]
    assert out["results"][0]["passed"] is False
    assert out["hard_pass2_accuracy"] == 0.0


def test_solver_exception_recorded_as_zero_without_crash():
    questions = [_easy(task_id="e1"), _easy(question="Who lost?", answer="Celtics", task_id="e2")]
    answers = _gold_solver(questions)

    def solver(question, guidelines):
        if question == "Who won?":
            raise RuntimeError("boom")
        return answers(question, guidelines)

    out = run_benchmark(solver, questions)
    assert out["results"][0] == {
        "task_id": "e1",
        "level": "easy",
        "attempts": 1,
        "scores": [0.0],
        "errors": ["RuntimeError: boom"],
        "passed": False,
    }
    assert out["results"][1]["passed"] is True
    assert out["easy_accuracy"] == 0.5


def test_hard_solver_exception_on_second_attempt_fails():
    questions = [_hard()]
    calls = {"n": 0}
    answers = _gold_solver(questions)

    def solver(question, guidelines):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return answers(question, guidelines)

    out = run_benchmark(solver, questions, hard_attempts=2)
    assert out["results"][0]["scores"] == [1.0, 0.0]
    assert out["results"][0]["errors"] == ["RuntimeError: boom"]
    assert out["results"][0]["passed"] is False


def test_hard_attempts_rejects_non_positive():
    questions = [_hard()]
    for bad in (0, -1, -10, True):
        with pytest.raises(ValueError):
            run_benchmark(_gold_solver(questions), questions,
                          hard_attempts=bad)


def test_hard_attempts_default_is_three():
    questions = [_hard()]

    def solver(question, guidelines):
        return "27.5"

    out = run_benchmark(solver, questions)
    assert out["results"][0]["attempts"] == 3
    assert out["results"][0]["scores"] == [1.0, 1.0, 1.0]
    assert out["results"][0]["errors"] == []


def test_hard_attempts_override():
    questions = [_hard()]

    def solver(question, guidelines):
        return "27.5"

    out = run_benchmark(solver, questions, hard_attempts=3)
    assert out["results"][0]["attempts"] == 3
    assert out["results"][0]["scores"] == [1.0, 1.0, 1.0]


def test_load_questions_reads_valid_jsonl(tmp_path):
    path = tmp_path / "q.jsonl"
    path.write_text(
        '{"task_id": "e1", "question": "Who?", "guidelines": "g", "level": "easy", "answer": "Lakers"}\n'
        '{"task_id": "h1", "question": "How many?", "guidelines": "g", "level": "hard", "answer": "27.5"}\n'
    )
    rows = load_questions(str(path))
    assert rows == [
        {"task_id": "e1", "question": "Who?", "guidelines": "g", "level": "easy", "answer": "Lakers"},
        {"task_id": "h1", "question": "How many?", "guidelines": "g", "level": "hard", "answer": "27.5"},
    ]


def test_load_questions_rejects_row_missing_key(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"task_id": "e1", "question": "Who?", "guidelines": "g", "level": "easy"}\n')
    with pytest.raises(ValueError):
        load_questions(str(path))


def test_load_questions_rejects_bad_level(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        '{"task_id": "e1", "question": "Who?", "guidelines": "g", "level": "medium", "answer": "Lakers"}\n'
    )
    with pytest.raises(ValueError):
        load_questions(str(path))
