import difflib
import math
import string

_CURRENCY = "$€£"


def _parse_number(s):
    t = s.strip()
    while t and t[0] in _CURRENCY:
        t = t[1:]
    t = t.strip().replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def _text_match(a, b):
    ca = " ".join(a.translate(str.maketrans("", "", string.punctuation)).split())
    cb = " ".join(b.translate(str.maketrans("", "", string.punctuation)).split())
    if ca == cb:
        return True
    return difflib.SequenceMatcher(None, ca, cb).ratio() > 0.95


def _close(a, b, rel_tol):
    pa = _parse_number(a.strip().lower())
    pb = _parse_number(b.strip().lower())
    if pa is not None and pb is not None:
        return math.isclose(pa, pb, rel_tol=rel_tol, abs_tol=0.0)
    return _text_match(a.strip().lower(), b.strip().lower())


def score_two_path(path_answers, truth, rel_tol=1e-4):
    if not path_answers:
        return {"consistent": False, "correct": False, "passed": False}
    pairs = [
        (path_answers[i], path_answers[j])
        for i in range(len(path_answers))
        for j in range(i + 1, len(path_answers))
    ]
    consistent = all(_close(a, b, rel_tol) for a, b in pairs)
    correct = all(_close(p, truth, rel_tol) for p in path_answers)
    return {"consistent": consistent, "correct": correct, "passed": consistent and correct}


def score_adversarial(predicted, truth):
    a = predicted.strip().lower()
    b = truth.strip().lower()
    pa = _parse_number(a)
    pb = _parse_number(b)
    if pa is not None and pb is not None:
        return math.isclose(pa, pb, rel_tol=1e-4, abs_tol=0.0)
    if ("," in a or ";" in a) and ("," in b or ";" in b):
        d = "," if "," in a or "," in b else ";"
        la = sorted([p.strip().lower() for p in a.split(d)])
        lb = sorted([p.strip().lower() for p in b.split(d)])
        if len(la) != len(lb):
            return False
        return all(score_adversarial(x, y) for x, y in zip(la, lb))
    return _text_match(a, b)


def score_task(task, model_output):
    if task.get("slice") == "adversarial":
        matched = score_adversarial(model_output.get("answer", ""), task.get("answer", ""))
        return {"passed": matched, "slice": "adversarial", "detail": {"matched": matched}}
    result = score_two_path(model_output.get("paths", []), task.get("answer", ""))
    return {
        "passed": result["passed"],
        "slice": "two-path",
        "detail": {"consistent": result["consistent"], "correct": result["correct"]},
    }
