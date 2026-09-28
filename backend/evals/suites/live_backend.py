"""Suite: live backend (explicit opt-in only).

Asks every runnable golden fixture question to a live backend and
scores the answers with the deterministic check (numbers + season
gate + names). Reports wall seconds and tool calls per question.

Without --live-backend every question is skipped with a labeled
reason; the suite never fabricates a backend result.
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


def _finish(res):
    emit("suite_finished", {"suite": "live_backend", "mode": res.mode,
                            "passed": res.passed, "failed": res.failed,
                            "skipped": res.skipped})
    return res


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
        res.notes.append("opt-in only: no live backend was probed")
        return _finish(res)
    if questions is None:
        res.fail("data-missing", "golden_questions.json not found; "
                                 "cannot run live probes")
        return _finish(res)

    res.mode = "live-backend"
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import duckdb
    except ImportError:
        res.skip("duckdb not installed; cannot build the live fixture")
        res.notes.append("install duckdb to probe a live backend")
        return _finish(res)
    import golden_warehouse as gw
    from live_backend import ask
    tmp = Path(tempfile.mkdtemp(prefix="evals-live-"))
    db = tmp / "fixture.duckdb"
    gw.build_fixture(db)
    con = duckdb.connect(str(db), read_only=True)
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
