#!/usr/bin/env python3
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

EVALS = Path(__file__).resolve().parent


def fold(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(c))


def load(split: str) -> list[dict]:
    if "heldout" in split:
        raise ValueError("held-out set must never be scored by the harness")
    path = EVALS / f"golden_qa_{split}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]


_DENIALS = (
    "incorrect", "wrong", "is not", "isn't", "isnt", "was not", "wasn't",
    "wasnt", "not correct", "false", "mistake", "correction", "retract",
)
_DENIAL_WINDOW = 12
_NEGATOR_RE = re.compile(r"(not|n't|never|no)\s*$")
_NEGATED_RE = re.compile(r"^\s*(wrong|incorrect|false|mistake)\b")


def contradicted(text: str, start: int, end: int) -> bool:
    for denial in _DENIALS:
        for occurrence in re.finditer(re.escape(denial), text):
            first, last = occurrence.start(), occurrence.end()
            if _NEGATOR_RE.search(text[max(0, first - 6):first]):
                continue
            if _NEGATED_RE.match(text[last:last + 10]):
                continue
            if first - end <= _DENIAL_WINDOW and start - last <= _DENIAL_WINDOW:
                return True
    return False


def _match_spans(text: str, expected: str) -> list[tuple[int, int]]:
    if not any(char.isdigit() for char in expected):
        return [(match.start(), match.end()) for match in
                re.finditer(re.escape(expected), text)]
    return [(match.start(), match.end()) for match in re.finditer(
        r"(?<![\d.])" + re.escape(expected) + r"(?![\d.])", text)]


def matched(text: str, expected: str) -> bool:
    return any(not contradicted(text, start, end)
               for start, end in _match_spans(text, expected))


def score_item(item: dict, answer: str) -> dict:
    text = fold(answer)
    alts = item.get("exact", [])
    missing_alt = [] if not alts else (
        [] if any(matched(text, fold(e)) for e in alts)
        else list(alts))
    missing_all = [e for e in item.get("exact_all", [])
                   if not matched(text, fold(e))]
    missing_names = [n for n in item.get("must_contain", [])
                     if not matched(text, fold(n))]
    any_of = item.get("any_of", [])
    if any_of and not any(matched(text, fold(n)) for n in any_of):
        missing_names = [*missing_names, f"any_of:{'/'.join(any_of)}"]
    missing_exact = missing_alt + missing_all
    return {"id": item["id"], "pass": not (missing_exact or missing_names),
            "missing_exact": missing_exact, "missing_names": missing_names}


def score_split(split: str, answers: dict[str, str]) -> dict:
    items = load(split)
    rows = [score_item(item, answers.get(item["id"], "")) for item in items]
    return {"split": split, "rows": rows}


def wilson(passed: int, total: int) -> tuple[float, float]:
    if not total:
        return (0.0, 0.0)
    z = 1.96
    p = passed / total
    denom = 1 + z * z / total
    center = p + z * z / (2 * total)
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (max(0.0, (center - margin) / denom),
            min(1.0, (center + margin) / denom))


def report(results: list[dict]) -> dict:
    rows = [row for result in results for row in result["rows"]]
    passed = sum(1 for row in rows if row["pass"])
    lo, hi = wilson(passed, len(rows))
    return {"n": len(rows), "passed": passed,
            "pass_rate": passed / len(rows) if rows else 0.0,
            "ci95": [round(lo, 3), round(hi, 3)],
            "failed_ids": [row["id"] for row in rows if not row["pass"]]}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", required=True)
    ap.add_argument("--splits", default="dev,test")
    args = ap.parse_args(argv)
    answers = json.loads(Path(args.answers).read_text())
    results = [score_split(split.strip(), answers)
               for split in args.splits.split(",")]
    output = report(results)
    output["splits"] = {result["split"]: [row["id"] for row in result["rows"]
                                          if row["pass"]]
                        for result in results}
    print(json.dumps(output, indent=1))
    return 0 if not output["failed_ids"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
