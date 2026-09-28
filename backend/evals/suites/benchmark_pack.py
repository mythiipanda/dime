"""Suite: benchmark pack (existing local pack, hermetic half).

Runs backend/tests/benchmark/test_benchmark_pack.py through the
pytest-free driver: scenario-file integrity plus the assertion engine
(check_text / check_budget / check_trajectory / grounding) on
fabricated transcripts. No network.

The live SSE half of the pack (runner.py against a backend) belongs to
the live_backend suite and is an explicit opt-in.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from suites import SuiteResult, load_test_module, drive_tests  # noqa: E402
from trace import emit  # noqa: E402

PACK_TEST = (Path(__file__).resolve().parent.parent.parent / "tests"
             / "benchmark" / "test_benchmark_pack.py")


def run(ctx):
    res = SuiteResult(name="benchmark_pack", mode="hermetic")
    emit("suite_started", {"suite": "benchmark_pack", "mode": "hermetic"})
    module, err = load_test_module(PACK_TEST)
    if err:
        res.fail("load-pack", f"could not load benchmark pack test: {err}")
        return res
    passed, failed, skipped, failures = drive_tests(module, prefix="pack:")
    for _ in range(passed):
        res.ok()
    for f in failures:
        res.fail(f["id"], f["detail"][:300])
    for _ in range(skipped):
        res.skip("pack test skipped")
    res.notes.append("hermetic half only: scenario integrity + assertion "
                     "engine on fabricated transcripts; live SSE runs are "
                     "the live_backend suite's job (--live-backend)")
    emit("suite_finished", {"suite": "benchmark_pack", "mode": res.mode,
                            "passed": res.passed, "failed": res.failed,
                            "skipped": res.skipped})
    return res
