"""Suite: live backend (explicit opt-in only).

Asks every runnable golden fixture question to a live backend and
scores the answers with the deterministic check (numbers + season
gate + names). Reports wall seconds and tool calls per question.

Warehouse contract (the point of this suite): the backend under test
must serve the SAME fixture warehouse the harness grades against.
The operator points the backend at the stable fixture file with the
production mechanism (DIME_WAREHOUSE env var) BEFORE the run; the
suite verifies via GET {base}/api/revision that the backend's
startup-frozen warehouse sha256 equals the fixture file's sha256, and
grades NOTHING until that check passes. A backend serving any other
warehouse (production, canonical, stale copy) fails every question
with `warehouse-unverified` and the report is labeled INVALID.

Without --live-backend every question is skipped with a labeled
reason; the suite never fabricates a backend result.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from suites import SuiteResult, load_live_client  # noqa: E402
from trace import emit  # noqa: E402
import scoring  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"


def _finish(res):
    emit("suite_finished", {"suite": "live_backend", "mode": res.mode,
                            "passed": res.passed, "failed": res.failed,
                            "skipped": res.skipped})
    return res


def _unverified(res, runnable, detail):
    """Mark the whole live run INVALID: no grading without verification."""
    res.mode = "live-backend-unverified"
    res.ledger = "signal"
    for q in runnable:
        res.fail(q["id"], f"warehouse-unverified: {detail}")
    res.notes.append("INVALID: no live answer was graded — the backend's "
                     "warehouse identity could not be verified against the "
                     "grading fixture. Point the backend at the fixture "
                     "(DIME_WAREHOUSE) and restart it, then re-run.")
    emit("warehouse_unverified", {"suite": "live_backend",
                                  "detail": detail[:300]})
    return _finish(res)


def run(ctx):
    res = SuiteResult(name="live_backend", mode="skipped")
    emit("suite_started", {"suite": "live_backend", "mode": "skipped"})
    base = ctx.get("live_backend")
    # The opt-in check comes before ANY file read: the default run must
    # never touch data files or raise FileNotFoundError here.
    try:
        questions = json.loads(
            (DATA / "golden_questions.json").read_text())["questions"]
    except FileNotFoundError:
        questions = None
    runnable = [q for q in (questions or [])
                if q.get("warehouse") == "fixture"
                and q.get("status") != "stubbed"]
    if not base:
        if questions is None:
            res.skip("opt-in only: no live backend probed "
                     "(golden_questions.json unavailable)")
        else:
            for q in runnable:
                res.skip(f"{q['id']}: needs --live-backend URL")
        res.notes.append("opt-in only: no live backend was probed; "
                         "no answer-quality signal collected")
        return _finish(res)
    if questions is None:
        res.fail("data-missing", "golden_questions.json not found; "
                                 "cannot run live probes")
        return _finish(res)

    try:
        import duckdb
    except ImportError:
        res.skip("duckdb not installed; cannot build the live fixture")
        res.notes.append("install duckdb to probe a live backend")
        return _finish(res)

    client = load_live_client()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import golden_warehouse as gw

    # Stable fixture (not a per-run tempdir): the operator points the
    # backend at this exact file BEFORE the run, so verification below
    # is meaningful.
    try:
        fixture, fixture_sha = client.ensure_fixture()
    except RuntimeError as exc:
        res.fail("fixture-build", str(exc))
        return _finish(res)

    # Verify BEFORE grading: the backend must report serving this file.
    verified, detail, _identity = client.verify_warehouse(base, fixture_sha)
    if not verified:
        return _unverified(res, runnable, detail)

    res.mode = "live-backend"
    res.ledger = "signal"
    res.notes.append(f"warehouse verified: {detail} "
                     f"(fixture: {fixture.name})")
    ask = client.ask
    con = duckdb.connect(str(fixture), read_only=True)
    try:
        for q in runnable:
            qid = q["id"]
            emit("question_asked", {"suite": "live_backend", "qid": qid,
                                   "question": q["question"]})
            values = gw._verifier_values(con, q)
            if values is None:
                res.fail(qid, "oracle null; cannot score")
                continue
            flat = gw._flatten(values, q.get("multi_row"))
            exp = {"season": q["expect"].get("season"), "numbers": [],
                   "names": []}
            for i in q["expect"].get("numbers_from", []):
                exp["numbers"].append(round(float(flat[i]), 2))
            for i in q["expect"].get("names_from", []):
                exp["names"].append(str(flat[i]))
            exp["names"].extend(q["expect"].get("names", []))
            try:
                ans = ask(base, q["question"])
            except Exception as exc:
                res.fail(qid, f"backend ask failed: {exc}")
                continue
            ok, detail = scoring.check_answer(exp, ans["text"])
            emit("answer_received",
                 {"qid": qid, "seconds": ans["seconds"],
                  "tool_calls": ans["tool_calls"],
                  "streamed_chars": ans["streamed_chars"]})
            emit("verdict", {"qid": qid, "criterion": "live-answer",
                             "pass_bool": ok, "detail": detail[:200]})
            if ok:
                res.ok()
            else:
                res.fail(qid, f"live answer wrong ({detail})",
                         expected=exp, got=ans["text"][:300])
            res.notes.append(f"{qid}: {ans['seconds']}s, "
                             f"{ans['tool_calls']} tool calls")
    finally:
        con.close()
    return _finish(res)
