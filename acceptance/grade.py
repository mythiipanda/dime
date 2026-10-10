#!/usr/bin/env python
"""Grade a runner output JSONL against acceptance/corpus.jsonl.

The runner output JSONL must have one object per line with the fields
``id``, ``final_text``, ``citations`` (list), ``latency_ms`` and
``error``. Per-item rules:

- ``exact`` / ``compound``: pass when every ``expect_numbers`` value
  appears in ``final_text``, every ``must_contain`` string appears
  (case-insensitive) and no ``must_not_contain`` string appears.
- ``citation``: same as above plus at least one citation
  (``len(citations) > 0``).
- ``honest_gap``: pass when the corpus expects a refusal and the text
  admits the missing data ("don't have", "not available", "no data",
  "can't find", "cannot") while stating no confident stat; a stated
  confident stat (or a ``must_not_contain`` anchor) counts as a
  fabrication.
- ``scope``: pass when the text declines or redirects to the NBA.

The report (per-item verdicts plus aggregate metrics: accuracy,
citation_rate, honest_gap_rate, fabrication_count, p50/p95 latency)
is written as Markdown.

Usage::

    python acceptance/grade.py --corpus C --run R --out report.md

Exits 0 when every corpus item passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys

ADMISSION_PHRASES = (
    "don't have",
    "not available",
    "no data",
    "can't find",
    "cannot",
)

DECLINE_PHRASES = (
    "can't",
    "cannot",
    "can not",
    "won't",
    "don't",
    "not able",
    "unable",
    "sorry",
    "decline",
    "out of scope",
    "outside the scope",
    "not within scope",
)

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
SEASON_RE = re.compile(r"\b(?:19|20)\d{2}-\d{2}\b")
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

ANSWERABLE_CATEGORIES = ("exact", "compound", "citation")


def load_jsonl(path):
    """Load a JSONL file into a list of dicts."""
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno}: invalid JSON: {exc}")
    return rows


def confident_stats(text):
    """Return numbers in ``text`` that read as stated statistics.

    Season keys (``2023-24``) and plain years (``2024``) are ignored so
    an honest admission that names a season is not mistaken for a stat.
    """
    cleaned = SEASON_RE.sub(" ", text)
    cleaned = YEAR_RE.sub(" ", cleaned)
    return NUMBER_RE.findall(cleaned)


def grade_item(item, row):
    """Grade one corpus ``item`` against one runner ``row``.

    Returns ``(passed, reasons, fabrication)``.
    """
    reasons = []
    fabrication = False
    if row is None:
        return False, ["missing from run output"], False

    error = row.get("error")
    if error:
        return False, [f"runner error: {error}"], False

    text = row.get("final_text") or ""
    text_lower = text.lower()
    citations = row.get("citations") or []
    category = item.get("category", "")

    if category in ANSWERABLE_CATEGORIES:
        for value in item.get("expect_numbers") or []:
            if str(value) not in text:
                reasons.append(f"missing expected number: {value}")
        for needle in item.get("must_contain") or []:
            if needle.lower() not in text_lower:
                reasons.append(f"missing required text: {needle}")
        for needle in item.get("must_not_contain") or []:
            if needle.lower() in text_lower:
                reasons.append(f"forbidden text present: {needle}")
        if category == "citation" and len(citations) == 0:
            reasons.append("no citations provided")
        return (not reasons), reasons, False

    if category == "honest_gap":
        if item.get("expect_refusal") is not True:
            reasons.append("corpus item does not expect a refusal")
        if not any(phrase in text_lower for phrase in ADMISSION_PHRASES):
            reasons.append("does not admit missing data")
        for needle in item.get("must_not_contain") or []:
            if needle.lower() in text_lower:
                fabrication = True
                reasons.append(f"fabrication anchor present: {needle}")
        stats = confident_stats(text)
        if stats:
            fabrication = True
            reasons.append(f"states confident stat(s): {', '.join(stats)}")
        if fabrication:
            return False, reasons, True
        return (not reasons), reasons, False

    if category == "scope":
        declines = any(phrase in text_lower for phrase in DECLINE_PHRASES)
        redirects = "nba" in text_lower
        if not (declines or redirects):
            reasons.append("neither declines nor redirects to NBA")
        return (not reasons), reasons, False

    return False, [f"unknown category: {category}"], False


def percentile(sorted_values, fraction):
    """Linear-interpolated percentile of an already sorted list."""
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = (len(sorted_values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    weight = position - lower
    return float(sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight)


def grade_run(corpus, run_rows):
    """Grade every corpus item; returns per-item results and metrics."""
    by_id = {}
    for row in run_rows:
        row_id = row.get("id")
        if row_id in by_id:
            raise SystemExit(f"duplicate run id: {row_id}")
        by_id[row_id] = row
    corpus_ids = {item.get("id") for item in corpus}
    unexpected = [row_id for row_id in by_id if row_id not in corpus_ids]

    results = []
    fabrication_count = 0
    citation_with_data = 0
    citation_total = 0
    latencies = []
    category_stats = {}

    for item in corpus:
        category = item.get("category", "")
        row = by_id.get(item.get("id"))
        passed, reasons, fabrication = grade_item(item, row)
        if fabrication:
            fabrication_count += 1
        results.append(
            {
                "id": item.get("id"),
                "category": category,
                "passed": passed,
                "reasons": reasons,
                "fabrication": fabrication,
            }
        )
        stats = category_stats.setdefault(category, {"total": 0, "passed": 0})
        stats["total"] += 1
        if passed:
            stats["passed"] += 1
        if category == "citation":
            citation_total += 1
            if row is not None and len(row.get("citations") or []) > 0:
                citation_with_data += 1
        if row is not None:
            latency = row.get("latency_ms")
            if isinstance(latency, (int, float)) and not isinstance(latency, bool):
                latencies.append(float(latency))

    latencies.sort()
    total = len(results)
    passed_total = sum(1 for result in results if result["passed"])
    gap_stats = category_stats.get("honest_gap", {"total": 0, "passed": 0})

    metrics = {
        "accuracy": (passed_total / total) if total else 0.0,
        "passed_total": passed_total,
        "total": total,
        "citation_rate": (citation_with_data / citation_total) if citation_total else 0.0,
        "citation_total": citation_total,
        "citation_with_data": citation_with_data,
        "honest_gap_rate": (gap_stats["passed"] / gap_stats["total"]) if gap_stats["total"] else 0.0,
        "honest_gap_total": gap_stats["total"],
        "honest_gap_passed": gap_stats["passed"],
        "fabrication_count": fabrication_count,
        "latency_p50_ms": percentile(latencies, 0.50),
        "latency_p95_ms": percentile(latencies, 0.95),
        "unexpected_run_ids": unexpected,
        "category_stats": category_stats,
    }
    return results, metrics


def format_ms(value):
    if value is None:
        return "n/a"
    return f"{value:.1f} ms"


def render_report(results, metrics):
    """Render the Markdown report from graded results and metrics."""
    lines = [
        "# Acceptance grade report",
        "",
        "## Metrics",
        "",
        f"- accuracy: {metrics['accuracy'] * 100:.1f}% "
        f"({metrics['passed_total']}/{metrics['total']})",
        f"- citation_rate: {metrics['citation_rate'] * 100:.1f}% "
        f"({metrics['citation_with_data']}/{metrics['citation_total']} citation items carry citations)",
        f"- honest_gap_rate: {metrics['honest_gap_rate'] * 100:.1f}% "
        f"({metrics['honest_gap_passed']}/{metrics['honest_gap_total']})",
        f"- fabrication_count: {metrics['fabrication_count']}",
        f"- latency p50: {format_ms(metrics['latency_p50_ms'])}",
        f"- latency p95: {format_ms(metrics['latency_p95_ms'])}",
        "",
        "## Per-item results",
        "",
        "| id | category | verdict | reasons |",
        "|---|---|---|---|",
    ]
    for result in results:
        verdict = "PASS" if result["passed"] else "FAIL"
        if result["fabrication"]:
            verdict = "FAIL (fabrication)"
        reasons = "; ".join(result["reasons"]) if result["reasons"] else "-"
        reasons = reasons.replace("|", "\\|")
        lines.append(f"| {result['id']} | {result['category']} | {verdict} | {reasons} |")
    if metrics["unexpected_run_ids"]:
        lines += [
            "",
            "## Unexpected run rows",
            "",
            ", ".join(sorted(metrics["unexpected_run_ids"])),
        ]
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Grade a runner output JSONL against the acceptance corpus.")
    parser.add_argument("--corpus", required=True, help="path to corpus JSONL")
    parser.add_argument("--run", required=True, help="path to runner output JSONL")
    parser.add_argument("--out", required=True, help="path to write the Markdown report")
    args = parser.parse_args(argv)

    corpus = load_jsonl(args.corpus)
    run_rows = load_jsonl(args.run)
    results, metrics = grade_run(corpus, run_rows)
    report = render_report(results, metrics)
    pathlib.Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
