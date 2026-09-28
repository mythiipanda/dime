"""Mutation self-test for the live-eval warehouse contract (hermetic).

Proves, without any LLM or network beyond localhost, that the live path
grades the right thing:

  A. Backend serves a DIFFERENT warehouse than the grading fixture
     -> pre-grading verification refuses; every question fails with
        `warehouse-unverified`; the report is labeled INVALID; NOTHING
        is graded.
  B. Fixture is poisoned (one game's result flipped) and the backend is
     relaunched against the poisoned file (verification passes)
     -> grading runs and the now-stale correct answer FAILS. The suite's
        expected values track the fixture file, not hardcoded answers.
  C. Pristine fixture + backend serving it + correct answers
     -> all questions pass. The happy path works.

The "backend" is a tiny localhost HTTP server implementing the real
protocol the harness speaks: POST /api/v1/chat/stream (SSE
final_answer) and GET /api/revision (startup-frozen warehouse sha256,
as v2/api/routes.py serves). What this does NOT prove: that the real
backend's LLM answers from the warehouse it serves — that link is the
backend's own data path (DIME_WAREHOUSE -> shared/store.py) and needs
a live run with a model.

Scenarios A–C exercise the golden-question live suite; D–F exercise
the frontier live path (Instinct found the frontier live path broken at
a270ab1: it overwrote its candidate list with the verify_warehouse
bool, throwing TypeError before grading anything):

  D. Frontier + verified sha + correct answers -> every candidate is
     probed and graded; none fail. The pass set.
  E. Fixture poisoned, backend relaunched on the poisoned file
     (verification passes), canned answers stale from the pristine
     fixture -> poisoned candidates FAIL as grading failures while
     untouched candidates still pass. The fail set.
  F. Backend reports a DIFFERENT warehouse sha than the grading
     fixture -> mode live-backend-unverified, every candidate fails
     `warehouse-unverified`, report INVALID, nothing graded.

Run: python3 backend/evals/selftest_live_path.py
"""

from __future__ import annotations

import json
import shutil
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

EVALS = Path(__file__).resolve().parent
sys.path.insert(0, str(EVALS))

import duckdb  # noqa: E402
from live_backend import ensure_fixture, fixture_path, sha256_file  # noqa: E402
from suites import golden_warehouse as gw  # noqa: E402
from trace import new_run as trace_new_run  # noqa: E402
import suites.live_backend as live_suite  # noqa: E402
import suites.frontier as frontier_suite  # noqa: E402


class FakeBackend(BaseHTTPRequestHandler):
    canned: dict = {}
    reported_sha: str = ""

    def _send(self, code, body, ctype):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/revision":
            payload = {"revision": "fake",
                       "warehouse": {"warehouse_id": "configured-runtime",
                                     "sha256": type(self).reported_sha}}
            self._send(200, json.dumps(payload), "application/json")
        else:
            self._send(404, "{}", "application/json")

    def do_POST(self):
        if self.path == "/api/v1/chat/stream":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            text = type(self).canned.get(body.get("q", ""), "I don't know.")
            sse = ("event: final_answer\n"
                   "data: " + json.dumps({"text": text}) + "\n\n")
            self._send(200, sse, "text/event-stream")
        else:
            self._send(404, "{}", "application/json")

    def log_message(self, *a):
        pass


def runnable_questions():
    qs = json.loads((EVALS / "data" / "golden_questions.json")
                    .read_text())["questions"]
    return [q for q in qs if q.get("warehouse") == "fixture"
            and q.get("status") != "stubbed"]


def canned_answers(fixture):
    """Fabricated-correct answers for the CURRENT fixture ground truth."""
    con = duckdb.connect(str(fixture), read_only=True)
    try:
        out = {}
        for q in runnable_questions():
            flat = gw._flatten(gw._verifier_values(con, q), q.get("multi_row"))
            out[q["question"]] = gw._fill(q["fabricate"]["correct"], flat)
        return out
    finally:
        con.close()


def frontier_canned_answers(fixture):
    """Fabricated-correct answers for frontier candidates, grounded in the
    CURRENT fixture: runs each candidate's verifier SQL, then renders an
    answer carrying exactly the expected numbers/names/season, so the
    deterministic scorer passes. Candidates whose oracle is null are
    verify-gated (never probed) and skipped here too."""
    con = duckdb.connect(str(fixture), read_only=True)
    try:
        out = {}
        for c in frontier_suite.generate():
            try:
                rows = con.execute(c["verifier_sql"]).fetchall()
            except Exception:
                continue
            if c["expect"].get("multi_row"):
                vals = [tuple(r) for r in rows]
            else:
                vals = (list(rows[0]) if rows and rows[0][0] is not None
                        else None)
            if vals is None:
                continue  # verify-gated; never probed
            flat = [x for row in
                    (vals if c["expect"].get("multi_row") else [vals])
                    for x in row]
            nums = [round(float(flat[i]), 2)
                    for i in c["expect"].get("numbers_from", [])]
            names = [str(flat[i]) for i in c["expect"].get("names_from", [])]
            parts = ([f"in the {c['expect']['season']} season"]
                     if c["expect"].get("season") else [])
            parts += [str(n) for n in names] + [str(n) for n in nums]
            out[c["question"]] = " ".join(parts)
        return out
    finally:
        con.close()


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        raise AssertionError(f"self-test failed: {name} {detail}")


def main():
    trace_new_run({"selftest": "live-path"})
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeBackend)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        # ---- pristine fixture ----
        fixture, fsha = ensure_fixture(rebuild=True)
        pristine_canned = canned_answers(fixture)
        FakeBackend.canned = pristine_canned

        # ---- Scenario A: backend serves a DIFFERENT warehouse ----
        print("A. backend serves a different warehouse than the fixture")
        poison_copy = fixture.parent / "selftest-poison-copy.duckdb"
        shutil.copy(fixture, poison_copy)
        con = duckdb.connect(str(poison_copy))
        con.execute("UPDATE silver_hist_gamelogs SET pts = pts + 500 "
                    "WHERE team_abbreviation = 'ARC'")
        con.close()
        FakeBackend.reported_sha = sha256_file(poison_copy)
        res = live_suite.run({"live_backend": base})
        check("mode is live-backend-unverified", res.mode == "live-backend-unverified", res.mode)
        check("nothing graded (0 passed)", res.passed == 0, f"passed={res.passed}")
        check("all 8 questions failed", res.failed == 8, f"failed={res.failed}")
        check("failures are warehouse-unverified",
              all("warehouse-unverified" in f["detail"] for f in res.failures))
        check("report labeled INVALID",
              any("INVALID" in n for n in res.notes))
        check("ledger is signal", res.ledger == "signal")
        poison_copy.unlink()

        # ---- Scenario B: poison the fixture, backend relaunched on it ----
        print("B. fixture poisoned (one ARC win flipped), backend relaunched")
        con = duckdb.connect(str(fixture))
        gd = con.execute(
            "SELECT DISTINCT game_date FROM silver_hist_gamelogs "
            "WHERE team_abbreviation = 'ARC' AND _season = '2024-25' "
            "AND wl = 'W' LIMIT 1").fetchone()[0]
        con.execute("UPDATE silver_hist_gamelogs SET wl = 'L' "
                    "WHERE team_abbreviation = 'ARC' AND game_date = ?",
                    [gd])
        con.close()
        poisoned_sha = sha256_file(fixture)
        check("poison changed the file", poisoned_sha != fsha)
        FakeBackend.reported_sha = poisoned_sha  # backend relaunched on it
        FakeBackend.canned = pristine_canned     # answers now stale
        res = live_suite.run({"live_backend": base})
        check("verification passed (mode live-backend)", res.mode == "live-backend", res.mode)
        check("grading ran and failed on stale answers", res.failed >= 1,
              f"failed={res.failed}")
        g1 = [f for f in res.failures if f["id"] == "g1"]
        check("g1 (flipped game) failed", len(g1) == 1)
        check("failure is a grading failure, not infra",
              "live answer wrong" in g1[0]["detail"], g1[0]["detail"][:80])

        # ---- Scenario C: happy path ----
        print("C. pristine fixture, backend serving it, correct answers")
        fixture, fsha = ensure_fixture(rebuild=True)
        FakeBackend.reported_sha = fsha
        FakeBackend.canned = canned_answers(fixture)
        res = live_suite.run({"live_backend": base})
        check("mode is live-backend", res.mode == "live-backend", res.mode)
        check("all 8 pass", res.passed == 8 and res.failed == 0,
              f"pass={res.passed} fail={res.failed}")
        check("note records verification",
              any("warehouse verified" in n for n in res.notes))

        # ---- Scenario D: frontier live path, verified warehouse ----
        print("D. frontier --live-backend, verified sha, correct answers")
        herm = frontier_suite.run({})
        n_verified = herm.skipped  # hermetic: one skip per verified candidate
        check("frontier verify-gate keeps candidates",
              n_verified > 0, f"n={n_verified}")
        FakeBackend.reported_sha = fsha
        pristine_frontier_canned = frontier_canned_answers(fixture)
        check("canned answers exist for every verified candidate",
              len(pristine_frontier_canned) == n_verified,
              f"canned={len(pristine_frontier_canned)} n={n_verified}")
        FakeBackend.canned = pristine_frontier_canned
        res = frontier_suite.run({"live_backend": base})
        check("mode is live-backend", res.mode == "live-backend", res.mode)
        check("no TypeError: candidates graded, not overwritten",
              all("not iterable" not in f["detail"] for f in res.failures))
        check("all candidates graded (generation + probe pass counts)",
              res.passed == 2 * n_verified and res.failed == 0,
              f"pass={res.passed} fail={res.failed} n={n_verified}")
        check("note records verification",
              any("warehouse verified" in n for n in res.notes))
        check("ledger is signal", res.ledger == "signal")

        # ---- Scenario E: frontier against a POISONED fixture ----
        # Backend "relaunched" on the poisoned file: verification passes,
        # ground truth tracks the poisoned fixture, canned answers are
        # stale (correct for the pristine fixture) -> poisoned candidates
        # fail as grading failures; untouched candidates still pass.
        print("E. frontier against a poisoned fixture, backend relaunched")
        RETAINED = frontier_suite.RETAINED
        retained_backup = (RETAINED.read_text() if RETAINED.is_file()
                           else None)
        con = duckdb.connect(str(fixture))
        con.execute("UPDATE silver_hist_gamelogs SET pts = pts + 500 "
                    "WHERE team_abbreviation = 'ARC'")
        con.close()
        FakeBackend.reported_sha = sha256_file(fixture)
        FakeBackend.canned = pristine_frontier_canned  # now stale
        res = frontier_suite.run({"live_backend": base})
        if retained_backup is None:
            RETAINED.unlink(missing_ok=True)
        else:
            RETAINED.write_text(retained_backup)
        check("verification passed (mode live-backend)",
              res.mode == "live-backend", res.mode)
        grading_fails = [f for f in res.failures
                         if "pipeline missed" in f["detail"]]
        check("poisoned candidates fail", len(grading_fails) >= 1,
              f"grading_fails={len(grading_fails)}")
        check("failures are grading failures, not infra",
              len(grading_fails) == res.failed,
              f"fail={res.failed} grading={len(grading_fails)}")
        check("unaffected candidates still pass (pass set exercised)",
              res.passed > n_verified,  # generation ok's + probe passes
              f"passed={res.passed} n={n_verified}")

        # ---- Scenario F: frontier with a DIFFERENT warehouse ----
        print("F. frontier, backend serving a different warehouse (wrong sha)")
        bogus = fixture.parent / "selftest-frontier-bogus.duckdb"
        shutil.copy(fixture, bogus)
        bcon = duckdb.connect(str(bogus))
        # mutate the copy so it genuinely differs from the grading fixture
        bcon.execute("UPDATE silver_hist_gamelogs SET pts = pts + 1 "
                     "WHERE team_abbreviation = 'BRV'")
        bcon.close()
        FakeBackend.reported_sha = sha256_file(bogus)
        bogus.unlink()
        FakeBackend.canned = frontier_canned_answers(fixture)
        res = frontier_suite.run({"live_backend": base})
        check("mode is live-backend-unverified",
              res.mode == "live-backend-unverified", res.mode)
        check("nothing graded: only generation ok's passed",
              res.passed == n_verified,
              f"passed={res.passed} n={n_verified}")
        check("every candidate fails warehouse-unverified",
              res.failed == n_verified
              and all("warehouse-unverified" in f["detail"]
                      for f in res.failures),
              f"failed={res.failed} n={n_verified}")
        check("report labeled INVALID",
              any("INVALID" in n for n in res.notes))
        check("ledger is signal", res.ledger == "signal")
    finally:
        server.shutdown()
        # leave the workspace clean: pristine fixture for real runs
        ensure_fixture(rebuild=True)
    print("\nself-test OK: verification refuses wrong warehouses (INVALID), "
          "grading tracks fixture ground truth (poison fails), happy path "
          "passes; frontier live path grades candidates end-to-end when "
          "verified (D), fails poisoned candidates (E), and goes INVALID "
          "with nothing graded on sha mismatch (F).")


if __name__ == "__main__":
    main()
