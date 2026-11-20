import difflib
import math
import string

SCHEMA_FIELDS = ("task_id", "question", "guidelines", "level", "answer")
LEVELS = ("easy", "hard")
_CURRENCY = "$€£"


def _blank(value):
    return not isinstance(value, str) or not value.strip()


def validate_row(row):
    errors = []
    for field in SCHEMA_FIELDS:
        if _blank(row.get(field)):
            errors.append(field + " is missing or blank")
    level = row.get("level")
    if not _blank(level) and level not in LEVELS:
        errors.append("level must be one of " + ", ".join(LEVELS))
    tools = row.get("tools_required")
    if not isinstance(tools, list) or not tools:
        errors.append("tools_required must be a non-empty list")
    if _blank(row.get("pretraining_note")):
        errors.append("pretraining_note is missing or blank")
    return errors


def _parse_number(value):
    text = value.strip()
    while text and text[0] in _CURRENCY:
        text = text[1:]
    text = text.strip().replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _text_match(first, second):
    cleaned_first = " ".join(
        first.translate(str.maketrans("", "", string.punctuation)).split()
    )
    cleaned_second = " ".join(
        second.translate(str.maketrans("", "", string.punctuation)).split()
    )
    if cleaned_first == cleaned_second:
        return True
    return difflib.SequenceMatcher(None, cleaned_first, cleaned_second).ratio() > 0.95


def score_answer(predicted, truth, rel_tol=1e-4):
    first = predicted.strip().lower()
    second = truth.strip().lower()
    first_number = _parse_number(first)
    second_number = _parse_number(second)
    if first_number is not None and second_number is not None:
        return math.isclose(first_number, second_number, rel_tol=rel_tol, abs_tol=0.0)
    return _text_match(first, second)


def score_task(task, model_output):
    matched = score_answer(model_output.get("answer", ""), task.get("answer", ""))
    return {"passed": matched, "detail": {"matched": matched}}


def template_row():
    return {
        "task_id": "",
        "question": "",
        "guidelines": "",
        "level": "",
        "answer": "",
        "tools_required": [],
        "pretraining_note": "",
    }
