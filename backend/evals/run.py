"""Dime eval harness: one command, honest modes, pass/fail report.

Usage:
    python3 backend/evals/run.py [options]

Options:
    --suite NAME        run one suite (default: all)
    --live-llm          skill-finder suite calls a real model (gemini-3.5-flash-lite,
                        free tier) instead of replaying recorded outputs
    --live-judge        judge suite calls real judges instead of recorded verdicts
    --live-backend URL  run golden questions + benchmark pack against a live backend
    --warehouse PATH    real warehouse file for real-warehouse golden questions
                        (default: $DIME_WAREHOUSE; skipped when absent)
    --list              list suites and exit

Default run is fully hermetic: stdlib + duckdb only, no network, no LLM,
no warehouse file. Suites that need more are skipped with a labeled reason;
a skip is never a pass.
"""

import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "backend"))

from suites import SuiteResult  # noqa: E402
from trace import new_run as trace_new_run  # noqa: E402

SUITES = [
    ("golden_warehouse", "suites.golden_warehouse"),
    ("skill_finder", "suites.skill_finder"),
    ("judge", "suites.judge"),
    ("frontier", "suites.frontier"),
    ("regression_protected", "suites.regression_protected"),
    ("scorer_mirror", "suites.scorer_mirror"),
    ("benchmark_pack", "suites.benchmark_pack"),
    ("eval_prompts", "suites.eval_prompts"),
    ("live_backend", "suites.live_backend"),
    ("unit_tests", "suites.unit_tests"),
]


def _run_suite(name, module, ctx):
    import importlib
    t0 = time.time()
    try:
        mod = importlib.import_module(module)
        result = mod.run(ctx)
        result.seconds = round(time.time() - t0, 2)
        return result
    except Exception as exc:  # a crashing suite is a failure, reported plainly
        return SuiteResult(
            name=name, mode="error", passed=0, failed=1, skipped=0,
            seconds=round(time.time() - t0, 2),
            failures=[{"id": "suite-crash",
                       "detail": f"{type(exc).__name__}: {exc}\n"
                                 f"{traceback.format_exc(limit=5)}"}],
            notes=["suite raised instead of returning a result"])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Dime eval harness: one command.")
    ap.add_argument("--suite", default=None)
    ap.add_argument("--live-llm", action="store_true")
    ap.add_argument("--live-judge", action="store_true")
    ap.add_argument("--live-backend", default=None)
    ap.add_argument("--warehouse", default=None)
    ap.add_argument("--record", action="store_true",
                      help="capture live llm/judge prompts+responses into "
                           "recordings (needs --live-llm / --live-judge)")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    if args.list:
        for name, _ in SUITES:
            print(name)
        return 0

    ctx = {
        "live_llm": args.live_llm,
        "live_judge": args.live_judge,
        "live_backend": args.live_backend,
        "warehouse": args.warehouse or os.environ.get("DIME_WAREHOUSE"),
        "record": args.record,
        "evals_dir": HERE,
        "data_dir": HERE / "data",
        "repo": REPO,
    }
    run_id = trace_new_run(ctx)

    picked = [(n, m) for n, m in SUITES
              if args.suite is None or n == args.suite]
    if args.suite and not picked:
        print(f"unknown suite: {args.suite}", file=sys.stderr)
        return 2

    results = [_run_suite(n, m, ctx) for n, m in picked]

    # ---- report ----
    print(f"\n# Dime evals  run={run_id}")
    print(f"# default hermetic; live suites need their flags "
          f"(see --help)\n")
    total_pass = total_fail = total_skip = 0
    for r in results:
        total_pass += r.passed
        total_fail += r.failed
        total_skip += r.skipped
        mark = "PASS" if r.failed == 0 else "FAIL"
        if r.passed == 0 and r.failed == 0 and r.skipped > 0:
            mark = "SKIP"
        print(f"[{mark}] {r.name:<20} mode={r.mode:<16} "
              f"pass={r.passed} fail={r.failed} skip={r.skipped} "
              f"({r.seconds}s)")
        for note in r.notes:
            print(f"       note: {note}")
        for f in r.failures:
            print(f"       FAIL {f.get('id')}: {f.get('detail', '')[:300]}")
            exp, got = f.get("expected"), f.get("got")
            if exp is not None or got is not None:
                print(f"         expected: {exp}")
                print(f"         got:      {got}")
    print(f"\nTOTAL pass={total_pass} fail={total_fail} skip={total_skip}")
    print("modes: hermetic | recorded | fallback-only->skip | "
          "live-* (opt-in) | skipped")
    print("A green run never claims verification it did not perform: "
          "fallback-only and skipped suites report as SKIP, never PASS.")

    failing = [r.name for r in results if r.failed]
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
