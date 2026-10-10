#!/usr/bin/env python
"""Validate acceptance/corpus.jsonl.

Re-runs every non-empty ``gold_sql`` against the runtime warehouse in read-only
mode and asserts that the gold scalar it returns really does contain every entry
of ``expect_numbers``. Also enforces the corpus contract from step 1
(``acceptance/README.md`` §1.6) and the step 2 shape: 30 items, ids
``qa-0001``..``qa-0030``, 12 exact / 6 compound / 4 citation / 5 honest_gap /
3 scope, single read-only ``SELECT`` per gold, and no question copied from the
repo's existing eval packs.

Usage::

    python acceptance/validate_corpus.py
    python acceptance/validate_corpus.py --corpus acceptance/corpus.jsonl

Exits 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import Counter

try:
    import duckdb
except ImportError:  # pragma: no cover - environment guard
    sys.exit("duckdb is required: pip install duckdb")

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = REPO_ROOT / "acceptance" / "corpus.jsonl"
DEFAULT_WAREHOUSE = REPO_ROOT / "backend" / "data" / "warehouse-runtime.duckdb"
EVALS_DIR = REPO_ROOT / "backend" / "evals"

CATEGORIES = ("exact", "compound", "citation", "honest_gap", "scope")
GOLD_CATEGORIES = ("exact", "compound", "citation", "honest_gap")
EXPECTED_COUNTS = {
    "exact": 12,
    "compound": 6,
    "citation": 4,
    "honest_gap": 5,
    "scope": 3,
}
EXPECTED_TOTAL = 30
REQUIRED_FIELDS = ("id", "question", "category", "expect_refusal", "gold_sql", "notes")
LIST_FIELDS = ("expect_numbers", "must_contain", "must_not_contain")

FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|merge|create|drop|alter|truncate|attach|detach|copy|"
    r"export|import|install|load|call|pragma|set|reset|vacuum|begin|commit|"
    r"rollback|grant|revoke)\b",
    re.IGNORECASE,
)
EVALS_QUESTION_KEYS = ("question", "q", "query", "prompt", "input", "text")


class Failures:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def check(self, condition: bool, message: str) -> bool:
        if not condition:
            self.messages.append(message)
        return bool(condition)

    def __len__(self) -> int:
        return len(self.messages)


def load_corpus(path: pathlib.Path, fail: Failures) -> list[dict]:
    if not path.is_file():
        fail.check(False, f"corpus file not found: {path}")
        return []
    items: list[dict] = []
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    for lineno, raw in enumerate(raw_lines, start=1):
        if not raw.strip():
            fail.check(False, f"line {lineno}: blank line (JSONL must have no blanks)")
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            fail.check(False, f"line {lineno}: not valid JSON ({exc})")
            continue
        if not isinstance(item, dict):
            fail.check(False, f"line {lineno}: JSON value is not an object")
            continue
        items.append(item)
    return items


def check_shape(items: list[dict], fail: Failures) -> None:
    fail.check(
        len(items) == EXPECTED_TOTAL,
        f"expected {EXPECTED_TOTAL} items, found {len(items)}",
    )

    ids = [item.get("id") for item in items]
    duplicates = sorted(i for i, n in Counter(ids).items() if n > 1)
    fail.check(not duplicates, f"duplicate ids: {duplicates}")
    expected_ids = [f"qa-{n:04d}" for n in range(1, EXPECTED_TOTAL + 1)]
    fail.check(
        ids == expected_ids,
        "ids must be the stable sequence qa-0001..qa-0030 in order",
    )

    counts = Counter(item.get("category") for item in items)
    for category, expected in EXPECTED_COUNTS.items():
        fail.check(
            counts.get(category, 0) == expected,
            f"category {category}: expected {expected}, found {counts.get(category, 0)}",
        )

    for item in items:
        iid = item.get("id", "<no id>")
        for field in REQUIRED_FIELDS:
            fail.check(field in item, f"{iid}: missing required field {field!r}")
        for field in LIST_FIELDS:
            value = item.get(field, [])
            fail.check(
                isinstance(value, list)
                and all(isinstance(v, str) for v in value),
                f"{iid}: {field} must be a list of strings",
            )
        fail.check(
            isinstance(item.get("question"), str) and item["question"].strip() != "",
            f"{iid}: question must be a non-empty string",
        )
        fail.check(
            isinstance(item.get("notes"), str),
            f"{iid}: notes must be a string",
        )
        fail.check(
            isinstance(item.get("expect_refusal"), bool),
            f"{iid}: expect_refusal must be a bool",
        )
        fail.check(
            item.get("category") in CATEGORIES,
            f"{iid}: category {item.get('category')!r} not in {CATEGORIES}",
        )
        gold_category = item.get("expected_category_of_gold")
        fail.check(
            gold_category in GOLD_CATEGORIES,
            f"{iid}: expected_category_of_gold {gold_category!r} not in {GOLD_CATEGORIES}",
        )
        if item.get("category") == "scope":
            fail.check(
                item.get("expect_refusal") is True,
                f"{iid}: scope items must set expect_refusal=true",
            )
            fail.check(
                gold_category == "honest_gap",
                f"{iid}: scope items must have expected_category_of_gold='honest_gap'",
            )


def check_sql_is_read_only_single_select(item: dict, fail: Failures) -> None:
    iid = item["id"]
    sql = item.get("gold_sql") or ""
    if item.get("expect_refusal"):
        fail.check(
            sql.strip() == "",
            f"{iid}: expect_refusal=true requires an empty gold_sql",
        )
        return

    if not fail.check(sql.strip() != "", f"{iid}: gold_sql must not be empty"):
        return
    stripped = sql.strip()
    fail.check(
        stripped.upper().startswith(("SELECT", "WITH")),
        f"{iid}: gold_sql must be a single read-only SELECT/WITH statement",
    )
    fail.check(
        ";" not in stripped.rstrip(";"),
        f"{iid}: gold_sql must be a single statement (found an internal semicolon)",
    )
    found = FORBIDDEN_SQL.search(stripped)
    fail.check(
        found is None,
        f"{iid}: gold_sql contains the write/DDL keyword {found.group(0)!r}"
        if found
        else "",
    )
    fail.check(
        bool(item.get("expect_numbers") or item.get("must_contain")),
        f"{iid}: needs at least one of expect_numbers / must_contain to be checkable",
    )


def run_gold(con, sql: str) -> str:
    result = con.execute(sql)
    rows = result.fetchall()
    if len(rows) != 1:
        raise AssertionError(f"expected 1 row, got {len(rows)}")
    if len(rows[0]) != 1:
        raise AssertionError(f"expected 1 column, got {len(rows[0])}")
    value = rows[0][0]
    if value is None:
        raise AssertionError("gold_sql returned NULL")
    return str(value)


def check_gold_values(items: list[dict], warehouse: pathlib.Path, fail: Failures) -> dict:
    summary: dict[str, str] = {}
    if not warehouse.is_file():
        fail.check(False, f"warehouse not found: {warehouse}")
        return summary

    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        for item in items:
            iid = item.get("id", "<no id>")
            if item.get("expect_refusal"):
                summary[iid] = "<refusal>"
                continue
            try:
                gold = run_gold(con, item["gold_sql"])
            except Exception as exc:  # noqa: BLE001 - report, do not abort the pass
                fail.check(False, f"{iid}: gold_sql failed: {exc}")
                continue
            summary[iid] = gold
            expect_numbers = item.get("expect_numbers") or []
            if not expect_numbers:
                fail.check(
                    bool(item.get("must_contain")),
                    f"{iid}: numeric-looking gold {gold!r} needs expect_numbers",
                )
            for number in expect_numbers:
                fail.check(
                    number.lower() in gold.lower(),
                    f"{iid}: expect_numbers {number!r} is not in gold {gold!r}",
                )
            if item.get("category") == "compound":
                fail.check(
                    "," in gold,
                    f"{iid}: compound gold must be a '<v1>,<v2>' string, got {gold!r}",
                )
    finally:
        con.close()
    return summary


def check_questions_are_original(items: list[dict], fail: Failures) -> None:
    if not EVALS_DIR.is_dir():
        return
    seen: dict[str, str] = {}
    for path in sorted(EVALS_DIR.glob("*.jsonl")):
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            for key in EVALS_QUESTION_KEYS:
                value = record.get(key)
                if isinstance(value, str) and value.strip():
                    seen[normalize_question(value)] = f"{path.name}:{key}"
    for item in items:
        normalized = normalize_question(item.get("question", ""))
        origin = seen.get(normalized)
        fail.check(
            origin is None,
            f"{item['id']}: question is copied from an existing eval pack ({origin})",
        )


def normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question).strip().lower()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", type=pathlib.Path, default=DEFAULT_CORPUS)
    parser.add_argument("--warehouse", type=pathlib.Path, default=DEFAULT_WAREHOUSE)
    parser.add_argument(
        "--show-gold",
        action="store_true",
        help="print each item's computed gold scalar",
    )
    args = parser.parse_args(argv)

    fail = Failures()
    items = load_corpus(args.corpus, fail)
    if items:
        check_shape(items, fail)
        check_questions_are_original(items, fail)
        for item in items:
            if "id" in item:
                check_sql_is_read_only_single_select(item, fail)
        summary = check_gold_values(items, args.warehouse, fail)
        if args.show_gold:
            for item in items:
                iid = item.get("id", "<no id>")
                print(f"{iid:9s} {item.get('category', '?'):11s} {summary.get(iid, '<none>')}")

    counts = Counter(item.get("category") for item in items)
    print(f"corpus : {args.corpus}")
    print(f"items  : {len(items)}")
    print(f"mix    : {dict(sorted(counts.items()))}")

    if len(fail):
        print(f"\nFAILED with {len(fail)} problem(s):", file=sys.stderr)
        for message in fail.messages:
            print(f"  - {message}", file=sys.stderr)
        return 1
    print("OK: all gold_sql executed and every expect_numbers matched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())