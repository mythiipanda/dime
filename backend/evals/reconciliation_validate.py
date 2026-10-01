import json
import re
import sys

_TASK_ID = re.compile(r"^(rec2p|reca)-\d{3}$")
_SLICES = frozenset({"two-path", "adversarial"})
_LEVELS = frozenset({"easy", "hard"})
_TEXT_FIELDS = ("task_id", "question", "guidelines", "level", "answer")


def _blank(value):
    return not isinstance(value, str) or value.strip() == ""


def _path_problems(paths):
    problems = []
    if not isinstance(paths, list) or len(paths) < 2:
        return ["expected_paths needs at least 2 entries"]
    for entry in paths:
        if not isinstance(entry, dict):
            problems.append("expected_paths entry is not an object")
            continue
        for key in ("name", "sql"):
            if _blank(entry.get(key)):
                problems.append(f"expected_paths entry has empty {key}")
    return problems


def validate_row(row):
    problems = []
    task_id = row.get("task_id")
    task_slice = row.get("slice")
    if not isinstance(task_id, str) or not _TASK_ID.match(task_id):
        problems.append("task_id must look like rec2p-NNN or reca-NNN")
    if task_slice not in _SLICES:
        problems.append("slice must be two-path or adversarial")
    if isinstance(task_id, str) and task_slice in _SLICES:
        if task_id.startswith("rec2p") != (task_slice == "two-path"):
            problems.append("task_id prefix must match slice")
    if row.get("level") not in _LEVELS:
        problems.append("level must be easy or hard")
    for field in _TEXT_FIELDS:
        if _blank(row.get(field)):
            problems.append(f"{field} must be a non-empty string")
    if task_slice == "two-path" or "expected_paths" in row:
        problems.extend(_path_problems(row.get("expected_paths")))
    if task_slice == "two-path" and _blank(row.get("resolution_notes")):
        problems.append("resolution_notes must be a non-empty string")
    return problems


def validate_file(path):
    errors = []
    seen = set()
    total = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            row = json.loads(line)
            problems = validate_row(row)
            task_id = row.get("task_id")
            if task_id in seen:
                problems.append("task_id is duplicated")
            seen.add(task_id)
            if problems:
                errors.append({"task_id": task_id, "problems": problems})
    return {"total": total, "valid": total - len(errors), "invalid": len(errors), "errors": errors}


if __name__ == "__main__":
    summary = validate_file(sys.argv[1])
    print(json.dumps(summary, indent=2))
    sys.exit(1 if summary["invalid"] else 0)
