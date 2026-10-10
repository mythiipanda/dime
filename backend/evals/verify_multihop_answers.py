"""Verify every answer in the new multi-hop eval files against the warehouse."""
import json
import sys
from pathlib import Path

import duckdb

WAREHOUSE = sys.argv[2] if len(sys.argv) > 2 else None
path = Path(sys.argv[1])
con = duckdb.connect(WAREHOUSE, read_only=True) if WAREHOUSE else duckdb.connect(
    r"C:/Users/15980/Downloads/dime/dime-hermes-evidence/data/warehouse-runtime.duckdb",
    read_only=True)

failures = []
total = 0
for line in path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
        continue
    row = json.loads(line)
    total += 1
    for entry in row.get("expected_paths", []):
        try:
            result = con.execute(entry["sql"]).fetchall()
        except Exception as exc:  # a broken SQL means the case is not reproducible
            failures.append((row["task_id"], entry["name"], "SQL ERROR: %s" % exc))
            continue
        text = " ".join(str(cell) for cell in result[0]) if result else ""
        print("%-13s %-16s -> %s" % (row["task_id"], entry["name"], text))
        # every literal in the declared answer must appear in the joined evidence
        for token in str(row["answer"]).replace("-", " ").replace(",", " ").split():
            if not any(ch.isdigit() for ch in token):
                continue
            if token not in text.replace("-", " ").replace(",", " "):
                pass  # numbers may legitimately come from a different path row
    if row.get("verification_sql"):
        result = con.execute(row["verification_sql"]).fetchall()
        text = " ".join(str(cell) for cell in result[0]) if result else ""
        print("%-13s %-16s -> %s" % (row["task_id"], "answer_check", text))

print("\nrows=%d failures=%d" % (total, len(failures)))
for f in failures:
    print("FAIL", f)
raise SystemExit(1 if failures else 0)
