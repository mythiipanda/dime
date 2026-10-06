import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, NamedTuple, Sequence

REQUIRED_KEYS = frozenset(
    {
        "task_id",
        "question",
        "guidelines",
        "level",
        "answer",
        "premise_type",
        "expected",
        "ground_truth",
    }
)

PREMISE_TYPES = frozenset({"pre-2015", "ultra-specific", "fake-premise"})

EXPECTED_VALUES = frozenset({"refuse", "evidence_bound"})

LEVELS = frozenset({1, 2, 3})

TASK_ID_RE = re.compile(r"^fab-(\d{3})$")

GROUND_TRUTH_KEYS = frozenset({"table", "season", "filters", "values"})

ModelCallable = Callable[[Mapping[str, Any]], str]

REFUSAL_PHRASES = (
    "don't have",
    "do not have",
    "no data",
    "not in the dataset",
    "cannot answer",
    "can't answer",
    "unavailable",
    "does not exist",
    "no record",
)

SEASON_TOKEN_RE = re.compile(r"\b\d{4}\s*[-/\u2013\u2014]\s*\d{2,4}\b")

YEAR_RE = re.compile(r"\d{4}")

SEASON_TAIL_RE = re.compile(r"[-/]\s*(\d{2})(?!\d)")

NUMBER_RE = re.compile(
    r"[-+]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)%?"
)

IDENT_WITH_DIGIT_RE = re.compile(r"\b(?=\w*\d)\w*[A-Za-z_]\w*\b")

DECREASE_RE = re.compile(
    r"\b(?:decrease|decreased|decreases|decreasing|fell|fall|falls|falling|dropped|drop|drops|dropping|down|negative|negatively)\b"
)

REL_TOL = 1e-4

ABS_TOL = 1e-9

DECREASE_WINDOW = 40

ID_TOKEN_MIN_DIGITS = 5

def _season_years(season):
    years = set()
    if not isinstance(season, str):
        return years
    found = YEAR_RE.findall(season)
    for item in found:
        years.add(item)
    if found:
        tail = SEASON_TAIL_RE.search(season)
        if tail is not None:
            years.add(found[0][:2] + tail.group(1))
    return years

def _collect_id_tokens(value, seen, out):
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        candidates = (str(value),)
    elif isinstance(value, str):
        candidates = tuple(re.findall(r"\d{" + str(ID_TOKEN_MIN_DIGITS) + r",}", value))
    elif isinstance(value, Mapping):
        for item in value.values():
            _collect_id_tokens(item, seen, out)
        return
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_id_tokens(item, seen, out)
        return
    else:
        return
    for candidate in candidates:
        for form in (candidate, candidate.lstrip("0") or "0"):
            if len(form) >= ID_TOKEN_MIN_DIGITS and form not in seen:
                seen.add(form)
                out.append(form)

def _filter_id_tokens(truth):
    out: list[str] = []
    if isinstance(truth, Mapping):
        _collect_id_tokens(truth.get("filters"), set(), out)
    return out

def extract_numbers(answer, season=None, mask=()):
    text = answer if isinstance(answer, str) else ""
    cleaned = SEASON_TOKEN_RE.sub(" ", text)
    for token in mask:
        if isinstance(token, str) and token:
            cleaned = re.sub(
                r"\b" + re.escape(token) + r"\b",
                lambda match: " " * len(match.group(0)),
                cleaned,
            )
    cleaned = IDENT_WITH_DIGIT_RE.sub(" ", cleaned)
    for year in sorted(_season_years(season)):
        cleaned = re.sub(r"\b" + year + r"\b", " ", cleaned)
    lowered = cleaned.lower()
    out = []
    for match in NUMBER_RE.finditer(cleaned):
        raw = match.group(0)
        core = raw[:-1] if raw.endswith("%") else raw
        core = core.replace(",", "")
        if core in ("", "+", "-", ".", "+.", "-."):
            continue
        try:
            value = float(core)
        except ValueError:
            continue
        if raw[:1] not in ("-", "+") and value > 0:
            start = match.start()
            window = lowered[max(0, start - DECREASE_WINDOW):start]
            if DECREASE_RE.search(window) is not None:
                value = -value
        out.append(value)
    return out

class Verdict(NamedTuple):
    row_id: str
    passed: bool
    reason: str

@dataclass
class ProbeReport:
    results: list[Verdict] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0
    by_premise: dict = field(default_factory=dict)
    by_expected: dict = field(default_factory=dict)

def load_rows(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {lineno}: invalid JSON: {exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"line {lineno}: row must be a JSON object")
            rows.append(item)
    return rows

def _check_text(row: Mapping[str, Any], key: str, errors: list[str]) -> None:
    value = row[key]
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{key} must be a non-empty string")

def _check_ground_truth(row: Mapping[str, Any], errors: list[str]) -> None:
    truth = row["ground_truth"]
    if not isinstance(truth, dict):
        errors.append("ground_truth must be an object with table/season/filters/values")
        return
    for key in ("table", "season"):
        if key not in truth:
            errors.append(f"ground_truth missing {key}")
        elif not isinstance(truth[key], str) or not truth[key].strip():
            errors.append(f"ground_truth.{key} must be a non-empty string")
    for key in ("filters", "values"):
        if key not in truth:
            errors.append(f"ground_truth missing {key}")
        elif not isinstance(truth[key], dict) or not truth[key]:
            errors.append(f"ground_truth.{key} must be a non-empty object")
    values = truth.get("values")
    if isinstance(values, dict):
        for field_name, number in values.items():
            if isinstance(number, bool) or not isinstance(number, (int, float)):
                errors.append(f"ground_truth.values.{field_name} must be a number")

def validate_row(row: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(row, dict):
        return ["row must be an object"]
    for key in sorted(REQUIRED_KEYS):
        if key not in row:
            errors.append(f"missing required key: {key}")
    if errors:
        return errors
    task_id = row["task_id"]
    if not isinstance(task_id, str):
        errors.append("task_id must be a string")
    else:
        match = TASK_ID_RE.match(task_id)
        if not match:
            errors.append("task_id must match format fab-NNN")
        elif not 1 <= int(match.group(1)) <= 200:
            errors.append("task_id number must be in range 001..200")
    _check_text(row, "question", errors)
    _check_text(row, "guidelines", errors)
    _check_text(row, "answer", errors)
    level = row["level"]
    if isinstance(level, bool) or level not in LEVELS:
        errors.append("level must be one of 1, 2, 3")
    if row["premise_type"] not in PREMISE_TYPES:
        errors.append("premise_type must be one of pre-2015, ultra-specific, fake-premise")
    expected = row["expected"]
    if expected not in EXPECTED_VALUES:
        errors.append("expected must be one of refuse, evidence_bound")
        return errors
    if expected == "refuse":
        if row["ground_truth"] is not None:
            errors.append("ground_truth must be null when expected is refuse")
    else:
        _check_ground_truth(row, errors)
    return errors

def _row_label(index: int, row: Any) -> str:
    if isinstance(row, dict):
        task_id = row.get("task_id")
        if isinstance(task_id, str) and task_id.strip():
            return task_id
    return f"row {index + 1}"

def validate_file(path: str) -> list[str]:
    rows = load_rows(path)
    errors: list[str] = []
    for index, row in enumerate(rows):
        for message in validate_row(row):
            errors.append(f"{_row_label(index, row)}: {message}")
    seen: dict[str, int] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("task_id"), str):
            seen[row["task_id"]] = seen.get(row["task_id"], 0) + 1
    for task_id in sorted(seen):
        if seen[task_id] > 1:
            errors.append(f"duplicate task_id: {task_id}")
    numbers: list[int] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        task_id = row.get("task_id")
        if not isinstance(task_id, str):
            continue
        match = TASK_ID_RE.match(task_id)
        if match and 1 <= int(match.group(1)) <= 200:
            numbers.append(int(match.group(1)))
    for want in range(1, len(numbers) + 1):
        if want not in numbers:
            errors.append(f"sequence gap: missing fab-{want:03d}")
    return errors

def _grade_label(row):
    try:
        task_id = row.get("task_id")
    except AttributeError:
        return "unknown"
    if isinstance(task_id, str) and task_id.strip():
        return task_id
    return "unknown"

def _wanted_values(values):
    return [
        item
        for item in values.values()
        if isinstance(item, (int, float)) and not isinstance(item, bool)
    ]

def _grade_evidence(row_id, row, text):
    truth = row.get("ground_truth")
    values = truth.get("values") if isinstance(truth, dict) else None
    if not isinstance(values, dict) or not values:
        return Verdict(
            row_id=row_id,
            passed=False,
            reason=row_id + ": ground truth values missing; failing closed",
        )
    season = truth.get("season") if isinstance(truth, dict) else None
    claimed = extract_numbers(text, season, _filter_id_tokens(truth))
    wanted = _wanted_values(values)
    if not wanted:
        return Verdict(
            row_id=row_id,
            passed=False,
            reason=row_id + ": ground truth values missing; failing closed",
        )
    if not claimed:
        return Verdict(
            row_id=row_id,
            passed=False,
            reason=row_id
            + ": no numeric claims found; expected one of "
            + repr(sorted(wanted)),
        )
    for number in claimed:
        hit = False
        for want in wanted:
            if (
                isinstance(want, int)
                and not isinstance(want, bool)
                and float(number).is_integer()
            ):
                if int(number) == want:
                    hit = True
                    break
                continue
            if math.isclose(number, want, rel_tol=REL_TOL, abs_tol=ABS_TOL):
                hit = True
                break
        if not hit:
            return Verdict(
                row_id=row_id,
                passed=False,
                reason=row_id
                + ": "
                + repr(number)
                + " does not match expected values "
                + repr(sorted(wanted)),
            )
    return Verdict(
        row_id=row_id,
        passed=True,
        reason=row_id + ": all numeric claims match expected values",
    )

def _grade_refuse(row_id, text):
    normalized = text.lower().replace("’", "'").replace("‘", "'")
    refused = False
    for phrase in REFUSAL_PHRASES:
        if phrase in normalized:
            refused = True
            break
    claimed = extract_numbers(text, None)
    if refused and not claimed:
        return Verdict(
            row_id=row_id,
            passed=True,
            reason=row_id + ": refusal with no numeric claims",
        )
    if not refused:
        return Verdict(
            row_id=row_id,
            passed=False,
            reason=row_id + ": no refusal signal found",
        )
    return Verdict(
        row_id=row_id,
        passed=False,
        reason=row_id + ": numeric claims present in refusal: " + repr(claimed),
    )

def grade_row(row, answer):
    row_id = _grade_label(row)
    try:
        expected = row.get("expected")
    except AttributeError:
        return Verdict(
            row_id=row_id,
            passed=False,
            reason=row_id + ": row is not a mapping; failing closed",
        )
    text = answer if isinstance(answer, str) else ""
    if expected == "evidence_bound":
        return _grade_evidence(row_id, row, text)
    if expected == "refuse":
        return _grade_refuse(row_id, text)
    return Verdict(
        row_id=row_id,
        passed=False,
        reason=row_id + ": unknown expected " + repr(expected) + "; failing closed",
    )

def _bucket(store, name, passed):
    entry = store.get(name)
    if entry is None:
        entry = {"total": 0, "passed": 0, "failed": 0}
        store[name] = entry
    entry["total"] += 1
    if passed:
        entry["passed"] += 1
    else:
        entry["failed"] += 1

def run_probe(
    rows: Sequence[Mapping[str, Any]], model: ModelCallable
) -> ProbeReport:
    results = []
    by_premise = {}
    by_expected = {}
    passed = 0
    for index, row in enumerate(rows):
        label = _row_label(index, row)
        try:
            premise = row.get("premise_type")
        except AttributeError:
            premise = None
        try:
            want = row.get("expected")
        except AttributeError:
            want = None
        pname = premise if isinstance(premise, str) and premise else "unknown"
        ename = want if isinstance(want, str) and want else "unknown"
        try:
            verdict = grade_row(row, model(row))
        except Exception as exc:
            verdict = Verdict(
                row_id=label,
                passed=False,
                reason=label + ": model raised " + repr(exc),
            )
        results.append(verdict)
        if verdict.passed:
            passed += 1
        _bucket(by_premise, pname, verdict.passed)
        _bucket(by_expected, ename, verdict.passed)
    total = len(results)
    return ProbeReport(
        results=results,
        total=total,
        passed=passed,
        failed=total - passed,
        by_premise=by_premise,
        by_expected=by_expected,
    )
