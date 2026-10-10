import json
import math
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

import duckdb

WAREHOUSE = sys.argv[2] if len(sys.argv) > 2 else None
path = Path(sys.argv[1])
con = duckdb.connect(WAREHOUSE, read_only=True) if WAREHOUSE else duckdb.connect(
    r"C:/Users/15980/Downloads/dime/dime-hermes-evidence/data/warehouse-runtime.duckdb",
    read_only=True)

NUMBER_RUN = re.compile(r"[+-]?(?:\d(?:[\d,]*\d)?(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
GROUPED_INTEGER = re.compile(r"\A\d{1,3}(?:,\d{3})*\Z")
INNER_HYPHEN = re.compile(r"(?<=\d)-(?=\d)")

failures = []
total = 0


def number_runs(text):
    return NUMBER_RUN.findall(INNER_HYPHEN.sub(" ", str(text)))


def parse_run(token):
    if "e" in token or "E" in token:
        return None
    sign = "-" if token.startswith("-") else ""
    integer_part, _, fraction_part = token.lstrip("+-").partition(".")
    if "," in integer_part:
        if GROUPED_INTEGER.match(integer_part):
            integer_part = integer_part.replace(",", "")
        elif not fraction_part and all(part.isdigit() for part in integer_part.split(",")):
            return [Decimal(sign + part) for part in integer_part.split(",")]
        else:
            return None
    literal = sign + integer_part + ("." + fraction_part if fraction_part else "")
    try:
        return [Decimal(literal)]
    except InvalidOperation:
        return None


def literal_values(text):
    values = []
    unsupported = []
    for token in number_runs(text):
        parsed = parse_run(token)
        if parsed is None:
            unsupported.append(token)
        else:
            values.extend(parsed)
    return values, unsupported


def cell_values(cell):
    if cell is None or isinstance(cell, bool):
        return []
    if isinstance(cell, Decimal):
        return [cell]
    if isinstance(cell, int):
        return [Decimal(cell)]
    if isinstance(cell, float):
        return [Decimal(repr(cell))] if math.isfinite(cell) else []
    return literal_values(cell)[0]


def result_values(result):
    values = []
    for row in result:
        for cell in row:
            values.extend(cell_values(cell))
    return values


def render(result):
    return " | ".join(" ".join(str(cell) for cell in row) for row in result)


def fail(task_id, check, reason):
    failures.append((task_id, check, reason))


print("SCOPE numeric-literal presence only; entity, metric and value binding not certified")

for line in path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
        continue
    total += 1
    row_id = "<row %d>" % total
    try:
        row = json.loads(line)
    except Exception as exc:
        fail(row_id, "record", "UNREADABLE ROW: %s" % exc)
        continue
    if not isinstance(row, dict):
        fail(row_id, "record", "ROW IS NOT AN OBJECT")
        continue
    task_id = row.get("task_id", row_id)
    if isinstance(task_id, bool) or not isinstance(task_id, (str, int)):
        task_id = row_id
    required, unsupported = literal_values(row.get("answer", ""))
    for token in unsupported:
        fail(task_id, "answer", "UNSUPPORTED NUMERIC LITERAL %s" % token)
    paths = row.get("expected_paths")
    if paths is None:
        paths = []
    if not isinstance(paths, list) or any(not isinstance(entry, dict) for entry in paths):
        fail(task_id, "record", "MALFORMED expected_paths")
        paths = []
    verification_sql = row.get("verification_sql")
    if verification_sql is not None and (not isinstance(verification_sql, str)
                                         or not verification_sql.strip()):
        fail(task_id, "answer_check", "MALFORMED verification_sql")
        verification_sql = None
    if not paths and not verification_sql:
        fail(task_id, "record", "NO VERIFICATION QUERY")
        continue
    observed = []
    for entry in paths:
        name = entry.get("name", "path")
        if isinstance(name, bool) or not isinstance(name, (str, int)):
            name = "path"
        sql = entry.get("sql")
        if not isinstance(sql, str) or not sql.strip():
            fail(task_id, name, "MALFORMED SQL")
            continue
        try:
            result = con.execute(sql).fetchall()
        except Exception as exc:
            fail(task_id, name, "SQL ERROR: %s" % exc)
            continue
        if not result:
            fail(task_id, name, "EMPTY RESULT")
            continue
        print("%-13s %-16s -> %s" % (task_id, name, render(result)))
        observed.extend(result_values(result))
    if verification_sql:
        try:
            result = con.execute(verification_sql).fetchall()
        except Exception as exc:
            fail(task_id, "answer_check", "SQL ERROR: %s" % exc)
            result = None
        if result is not None:
            if not result:
                fail(task_id, "answer_check", "EMPTY RESULT")
            else:
                print("%-13s %-16s -> %s" % (task_id, "answer_check", render(result)))
                observed.extend(result_values(result))
    for value in required:
        if value not in observed:
            fail(task_id, "answer", "MISSING VALUE %s" % value)

print("\nrows=%d failures=%d" % (total, len(failures)))
for f in failures:
    print("FAIL", f)
raise SystemExit(1 if failures else 0)
