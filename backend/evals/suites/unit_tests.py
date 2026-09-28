"""Suite: unit tests (bounded, hermetic).

Two cheap gates over the backend tree:
  1. py_compile every .py under backend/app, backend/shared,
     backend/evals, backend/tests (syntax check; never imports).
  2. Import smoke test of the stdlib-only modules the harness depends
     on (skills catalog, scoring, golden warehouse helpers).

This is a smoke gate, not a full unit suite: real unit tests live with
the product code and its own runner.
"""

from __future__ import annotations

import importlib.util
import py_compile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from suites import SuiteResult  # noqa: E402
from trace import emit  # noqa: E402

TREES = ["app", "shared", "evals", "tests"]
SMOKE = [
    ("dime_skills", "app/skills.py", "catalog"),
    ("evals_scoring", "evals/scoring.py", "check_answer"),
]


def run(ctx):
    res = SuiteResult(name="unit_tests", mode="hermetic")
    emit("suite_started", {"suite": "unit_tests", "mode": "hermetic"})
    backend = Path(__file__).resolve().parent.parent.parent
    files = []
    for tree in TREES:
        files.extend(sorted((backend / tree).rglob("*.py")))
    bad = 0
    for f in files:
        try:
            py_compile.compile(str(f), doraise=True)
        except py_compile.PyCompileError as exc:
            bad += 1
            res.fail(f"compile:{f.relative_to(backend)}", str(exc)[:200])
    res.notes.append(f"py_compile: {len(files) - bad}/{len(files)} ok")
    if bad == 0:
        res.ok()

    for modname, rel, attr in SMOKE:
        try:
            spec = importlib.util.spec_from_file_location(
                modname, backend / rel)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            assert callable(getattr(mod, attr)), f"no {attr}"
            res.ok()
        except Exception as exc:
            res.fail(f"import:{rel}", f"{type(exc).__name__}: {exc}"[:200])
    emit("suite_finished", {"suite": "unit_tests", "mode": res.mode,
                            "passed": res.passed, "failed": res.failed,
                            "skipped": res.skipped})
    return res
