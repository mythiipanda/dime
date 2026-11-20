import json
import sys
from pathlib import Path

import duckdb

DEFAULT_WAREHOUSE = r"C:/Users/15980/Downloads/dime/dime-hermes-evidence/data/warehouse-runtime.duckdb"

def _evidence_text(result):
    return " ".join(str(cell) for cell in result[0]) if result else ""

def _normalized(text):
    return str(text).replace("-", " ").replace(",", " ")

def verify_case(row, execute_sql):
    task_id = row["task_id"]
    paths = row.get("expected_paths") or []
    failures = []
    lines = []

    if not paths:

        failures.append((task_id, "-", "NO EVIDENCE PATHS"))
        lines.append("%-13s %-16s -> %s" % (task_id, "-", "NO EVIDENCE PATHS"))
        return failures, lines

    evidence = []
    for entry in paths:
        try:
            result = execute_sql(entry["sql"])
        except Exception as exc:
            failures.append((task_id, entry["name"], "SQL ERROR: %s" % exc))
            continue
        text = _evidence_text(result)
        lines.append("%-13s %-16s -> %s" % (task_id, entry["name"], text))
        if not result:
            failures.append((task_id, entry["name"], "EMPTY EVIDENCE"))
            continue
        evidence.append(text)

    if evidence:
        joined = " ".join(evidence)
        haystack = _normalized(joined)
        for token in _normalized(row["answer"]).split():
            if not any(ch.isdigit() for ch in token):
                continue
            if token not in haystack:
                failures.append((task_id, "-", "MISSING NUMERAL: %s (evidence: %s)"
                                 % (token, joined)))

    if row.get("verification_sql"):
        result = execute_sql(row["verification_sql"])
        text = _evidence_text(result)
        lines.append("%-13s %-16s -> %s" % (task_id, "answer_check", text))

    return failures, lines

def main(argv):
    warehouse = argv[2] if len(argv) > 2 else None
    path = Path(argv[1])
    con = duckdb.connect(warehouse, read_only=True) if warehouse else duckdb.connect(
        DEFAULT_WAREHOUSE, read_only=True)

    failures = []
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        total += 1
        case_failures, lines = verify_case(row, lambda sql: con.execute(sql).fetchall())
        for text in lines:
            print(text)
        failures.extend(case_failures)

    print("\nrows=%d failures=%d" % (total, len(failures)))
    for f in failures:
        print("FAIL", f)
    raise SystemExit(1 if failures else 0)

if __name__ == "__main__":
    main(sys.argv)
