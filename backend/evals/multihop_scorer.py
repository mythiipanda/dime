import difflib
import math


def _parse_number(value):
    if isinstance(value, bool):
        return None
    try:
        return float(str(value).strip())
    except (ValueError, TypeError, AttributeError):
        return None


def _normalize(value):
    return " ".join(str(value).strip().lower().split())


def score(pred, gold):
    pred_num = _parse_number(pred)
    gold_num = _parse_number(gold)
    if pred_num is not None and gold_num is not None:
        if math.isclose(pred_num, gold_num, rel_tol=1e-4, abs_tol=0.0):
            return 1.0
        return 0.0
    if pred_num is not None or gold_num is not None:
        return 0.0
    ratio = difflib.SequenceMatcher(None, _normalize(pred), _normalize(gold)).ratio()
    if ratio > 0.95:
        return 1.0
    return 0.0


def score_batch(pairs):
    return [score(pred, gold) for pred, gold in pairs]
