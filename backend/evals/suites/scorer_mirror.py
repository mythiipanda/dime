"""Suite: canonical scorer mirror (honesty rule enforced).

Runs backend/tests/test_season_consistency_mirror.py through the
pytest-free driver. The mirror test looks up the canonical DimeBench
scorer (local dime-internal -> pinned GitHub blob, sha-verified ->
hermetic fallback port) and runs it over every fixture case.

Mode semantics (from the mirror test itself):
  canonical: the real scorer ran; verdicts are canonical verification.
  fallback-only: only the hermetic port ran; every case is reported as
    SKIP, never PASS. A green fallback-only run claims nothing about
    the canonical scorer.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from suites import SuiteResult, load_test_module  # noqa: E402
from suites import _Skipped  # noqa: E402
from trace import emit  # noqa: E402

MIRROR = (Path(__file__).resolve().parent.parent.parent / "tests"
          / "test_season_consistency_mirror.py")
CANON = "test_expected_outputs_match_canonical_scorer"


def run(ctx):
    res = SuiteResult(name="scorer_mirror", mode="hermetic")
    emit("suite_started", {"suite": "scorer_mirror", "mode": "hermetic"})
    module, err = load_test_module(MIRROR)
    if err:
        res.fail("load-mirror", f"could not load mirror test: {err}")
        return res

    # structural tests: run each once
    for attr in sorted(dir(module)):
        if not attr.startswith("test_") or attr == CANON:
            continue
        fn = getattr(module, attr)
        if not callable(fn):
            continue
        try:
            fn()
            res.ok()
        except _Skipped as s:
            res.skip(f"{attr}: {s.reason}")
        except AssertionError as exc:
            res.fail(attr, f"assertion: {exc}"[:300])
        except Exception as exc:
            res.fail(attr, f"{type(exc).__name__}: {exc}"[:300])

    # canonical verification test: run once, branch on its own verdict
    try:
        getattr(module, CANON)()
        res.ok()
        res.mode = "canonical"
        res.notes.append("canonical scorer ran (local checkout or "
                         "sha-verified pinned blob); verdicts are canonical "
                         "verification")
    except _Skipped as s:
        res.mode = "fallback-only"
        res.skip(f"{CANON}: {s.reason}")
        res.notes.append("fallback-only: canonical scorer unreachable; the "
                         "hermetic port's checks are reported as SKIP, not "
                         "PASS — a green run here claims nothing about the "
                         "canonical scorer")
    except AssertionError as exc:
        res.fail(CANON, f"assertion: {exc}"[:300])
    except Exception as exc:
        res.fail(CANON, f"{type(exc).__name__}: {exc}"[:300])

    emit("suite_finished", {"suite": "scorer_mirror", "mode": res.mode,
                            "passed": res.passed, "failed": res.failed,
                            "skipped": res.skipped})
    return res
