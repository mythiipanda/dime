import json

from backend.evals.multihop_scorer import score

_REQUIRED_KEYS = ("task_id", "question", "guidelines", "level", "answer")


def _validate(row):
    if not isinstance(row, dict):
        raise ValueError("row is not an object")
    for key in _REQUIRED_KEYS:
        if key not in row:
            raise ValueError("row missing " + key)
    if row["level"] not in ("easy", "hard"):
        raise ValueError("bad level")


def load_questions(path):
    questions = []
    with open(path) as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError("bad json") from exc
            _validate(row)
            questions.append(row)
    return questions


def _score_attempt(solver, question):
    try:
        return score(solver(question["question"], question["guidelines"]), question["answer"])
    except Exception:
        return 0.0


def _run_one(solver, question, hard_attempts):
    level = question["level"]
    n = 1 if level == "easy" else hard_attempts
    scores = [_score_attempt(solver, question) for _ in range(n)]
    return {
        "task_id": question["task_id"],
        "level": level,
        "attempts": n,
        "scores": scores,
        "passed": all(s == 1.0 for s in scores),
    }


def _split(results):
    groups = {"easy": [], "hard": []}
    for result in results:
        groups[result["level"]].append(result)
    return groups


def _accuracy(group):
    if not group:
        return 0.0
    return sum(1.0 for r in group if r["passed"]) / len(group)


def run_benchmark(solver, questions, hard_attempts=2):
    results = [_run_one(solver, q, hard_attempts) for q in questions]
    groups = _split(results)
    return {
        "results": results,
        "easy_accuracy": _accuracy(groups["easy"]),
        "hard_pass2_accuracy": _accuracy(groups["hard"]),
        "n_easy": len(groups["easy"]),
        "n_hard": len(groups["hard"]),
    }
