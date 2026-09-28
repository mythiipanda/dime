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
a live run with a model. Run: python3 backend/evals/selftest_live_path.py
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
    finally:
        server.shutdown()
        # leave the workspace clean: pristine fixture for real runs
        ensure_fixture(rebuild=True)
    print("\nself-test OK: verification refuses wrong warehouses (INVALID), "
          "grading tracks fixture ground truth (poison fails), happy path "
          "passes.")


if __name__ == "__main__":
    main()
