"""Suite: protected regression set (weakness-frontier backstop).

Loads data/frontier_retained.json — questions the pipeline has missed
before — and re-probes them. A retained question that now passes is a
fixed weakness (noted, stays protected); one that still fails is an open
regression (fails the suite).

Modes:
  hermetic (default): the protected set is listed but not probed; each
    entry is skipped with a labeled reason. An empty set passes
    vacuously with a note.
  --live-backend URL: every retained question must pass.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from suites import SuiteResult  # noqa: E402
from trace import emit  # noqa: E402
import scoring  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
RETAINED = DATA / "frontier_retained.json"


def run(ctx):
    res = SuiteResult(name="regression_protected", mode="hermetic")
    emit("suite_started", {"suite": "regression_protected",
                           "mode": "hermetic"})
    retained = json.loads(RETAINED.read_text()) if RETAINED.is_file() else []
    if not retained:
        res.ok()
        res.notes.append("protected set empty: no retained misses yet; "
                         "run frontier with --live-backend to mine some")
        emit("suite_finished", {"suite": "regression_protected",
                                "mode": res.mode, "passed": res.passed,
                                "failed": res.failed,
                                "skipped": res.skipped})
        return res

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import golden_warehouse as gw
    try:
        import duckdb
    except ImportError:
        res.mode = "skipped"
        res.skip("duckdb not installed; cannot re-verify retained misses "
                 "(pip install duckdb)")
        emit("suite_finished", {"suite": "regression_protected",
                                "mode": res.mode, "passed": res.passed,
                                "failed": res.failed,
                                "skipped": res.skipped})
        return res
    tmp = Path(tempfile.mkdtemp(prefix="evals-regr-"))
    db = tmp / "fixture.duckdb"
    gw.build_fixture(db)
    con = duckdb.connect(str(db), read_only=True)
    try:
        truths = {}
        for r in retained:
            try:
                rows = con.execute(r["verifier_sql"]).fetchall()
            except Exception as exc:
                res.fail(r["id"], f"retained verifier broken: {exc}")
                continue
            if r["expect"].get("multi_row"):
                truths[r["id"]] = [c for row in rows for c in row]
            elif rows and rows[0][0] is not None:
                truths[r["id"]] = list(rows[0])
            else:
                res.fail(r["id"], "retained oracle now null; fixture drift?")
    finally:
        con.close()

    base = ctx.get("live_backend")
    if not base:
        for r in retained:
            res.skip(f"{r['id']}: protected; needs --live-backend to re-probe")
            emit("question_asked", {"suite": "regression_protected",
                                   "qid": r["id"],
                                   "question": r["question"],
                                   "status": "protected-unprobed"})
        emit("suite_finished", {"suite": "regression_protected",
                                "mode": res.mode, "passed": res.passed,
                                "failed": res.failed,
                                "skipped": res.skipped})
        return res

    res.mode = "live-backend"
    from live_backend import ask
    for r in retained:
        if r["id"] not in truths:
            continue
        flat = truths[r["id"]]
        exp = {"season": r["expect"].get("season"), "numbers": [],
               "names": []}
        for i in r["expect"].get("numbers_from", []):
            exp["numbers"].append(round(float(flat[i]), 2))
        for i in r["expect"].get("names_from", []):
            exp["names"].append(str(flat[i]))
        try:
            ans = ask(base, r["question"])
        except Exception as exc:
            res.fail(r["id"], f"backend ask failed: {exc}")
            continue
        ok, detail = scoring.check_answer(exp, ans["text"])
        emit("verdict", {"qid": r["id"], "criterion": "protected-regression",
                         "pass_bool": ok})
        if ok:
            res.ok()
            res.notes.append(f"{r['id']}: previously-missed question now "
                             "passes (weakness fixed, stays protected)")
        else:
            res.fail(r["id"], f"OPEN REGRESSION: still failing ({detail})",
                     expected=exp, got=ans["text"][:200])
    emit("suite_finished", {"suite": "regression_protected", "mode": res.mode,
                            "passed": res.passed, "failed": res.failed,
                            "skipped": res.skipped})
    return res
