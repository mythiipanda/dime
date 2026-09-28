"""Suite: weakness-frontier mining (adopt 6).

Generates warehouse-grounded candidate questions from templates at three
explicit difficulty levels, runs each hidden verifier SQL against the
fixture warehouse (null oracle -> candidate rejected at generation), and
probes them against a live backend when --live-backend is set. Questions
the pipeline gets wrong are retained into data/frontier_retained.json,
which the regression_protected suite guards.

Modes:
  hermetic (default): generation + verification only; probing is skipped
    with a labeled reason (never claimed as probed).
  --live-backend URL: probes every candidate and retains misses.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from suites import SuiteResult, load_live_client  # noqa: E402
from trace import emit  # noqa: E402
import scoring  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
RETAINED = DATA / "frontier_retained.json"
GEN_SEED = 20260928

# (difficulty, question template, verifier template, expect spec)
TEMPLATES = [
    ("easy",
     "How many total points did {team} score in the {season} season?",
     "SELECT SUM(pts) FROM silver_hist_gamelogs "
     "WHERE team_abbreviation = '{abbr}' AND _season = '{season}'",
     {"numbers_from": [0], "names_from": [], "season": "{season}"}),
    ("easy",
     "How many games did {team} win in the {season} season?",
     "SELECT COUNT(DISTINCT game_date) FROM silver_hist_gamelogs "
     "WHERE team_abbreviation = '{abbr}' AND wl = 'W' "
     "AND _season = '{season}'",
     {"numbers_from": [0], "names_from": [], "season": "{season}"}),
    ("medium",
     "What was {team}'s true shooting percentage in the {season} season?",
     "SELECT SUM(pts) * 1.0 / (2 * (SUM(fga) + 0.44 * SUM(fta))) "
     "FROM silver_hist_gamelogs "
     "WHERE team_abbreviation = '{abbr}' AND _season = '{season}'",
     {"numbers_from": [0], "names_from": [], "season": "{season}"}),
    ("medium",
     "Who averaged the most assists per game for {team} in {season} "
     "(min 5 games)?",
     "SELECT player_name, SUM(ast) * 1.0 / COUNT(*) FROM "
     "silver_hist_gamelogs WHERE team_abbreviation = '{abbr}' "
     "AND _season = '{season}' GROUP BY 1 HAVING COUNT(*) >= 5 "
     "ORDER BY 2 DESC LIMIT 1",
     {"numbers_from": [1], "names_from": [0], "season": "{season}"}),
    ("hard",
     "Did {team} win more games in 2023-24 or 2024-25, and by how many?",
     "SELECT _season, COUNT(DISTINCT game_date) AS w FROM "
     "silver_hist_gamelogs WHERE team_abbreviation = '{abbr}' AND wl = 'W' "
     "GROUP BY _season ORDER BY _season",
     {"numbers_from": [1, 3], "names_from": [], "season": None,
      "multi_row": True}),
    ("hard",
     "Which season did {player} average more points per game, 2023-24 "
     "or 2024-25?",
     "SELECT _season, SUM(pts) * 1.0 / COUNT(*) FROM silver_hist_gamelogs "
     "WHERE player_name = '{player}' GROUP BY _season ORDER BY _season",
     {"numbers_from": [1, 3], "names_from": [], "season": None,
      "multi_row": True}),
]

TEAMS = [("Arcadia Arcs", "ARC", "Zane Mercer"),
         ("Briar Vales", "BRV", "Milo Kessler"),
         ("Coral Dunes", "CRD", "Jax Perrin"),
         ("Dusk Harbor", "DSK", "Eli Navarro")]
SEASONS = ["2023-24", "2024-25"]


def generate():
    rng = random.Random(GEN_SEED)
    cands = []
    for diff, qt, vt, expect in TEMPLATES:
        for team, abbr, player in TEAMS:
            for season in SEASONS:
                q = qt.format(team=team, abbr=abbr, player=player,
                              season=season)
                v = vt.format(team=team, abbr=abbr, player=player,
                              season=season)
                exp = {k: (vv.format(season=season) if isinstance(vv, str)
                           else vv)
                       for k, vv in expect.items()}
                cid = "f-" + hashlib.sha256(q.encode()).hexdigest()[:10]
                cands.append({"id": cid, "question": q, "verifier_sql": v,
                              "expect": exp, "difficulty": diff,
                              "generation": "frontier-gen1",
                              "warehouse": "fixture"})
    # dedupe identical questions
    seen, out = set(), []
    for c in cands:
        if c["question"] not in seen:
            seen.add(c["question"])
            out.append(c)
    return out


def run(ctx):
    res = SuiteResult(name="frontier", mode="hermetic")
    emit("suite_started", {"suite": "frontier", "mode": "hermetic"})
    try:
        import duckdb
    except ImportError:
        res.mode = "skipped"
        res.skip("duckdb not installed; cannot verify-gate candidates "
                 "(pip install duckdb)")
        emit("suite_finished", {"suite": "frontier", "mode": res.mode,
                                "passed": res.passed, "failed": res.failed,
                                "skipped": res.skipped})
        return res

    cands = generate()
    res.notes.append(f"generated {len(cands)} candidates "
                     f"(seed={GEN_SEED}, 3 difficulty levels)")

    # Stable fixture (not a per-run tempdir): live probing grades the
    # backend against THIS file, so the backend must serve it too (see
    # the warehouse verification below).
    client = load_live_client()
    try:
        fixture, fixture_sha = client.ensure_fixture()
    except RuntimeError as exc:
        res.fail("fixture-build", str(exc))
        return res
    con = duckdb.connect(str(fixture), read_only=True)
    verified = []
    try:
        for c in cands:
            try:
                rows = con.execute(c["verifier_sql"]).fetchall()
            except Exception as exc:
                res.fail(c["id"], f"verifier SQL invalid: {exc}")
                continue
            vals = ([tuple(r) for r in rows] if c["expect"].get("multi_row")
                    else (list(rows[0]) if rows and rows[0][0] is not None
                          else None))
            if vals is None:
                emit("frontier_rejected",
                     {"qid": c["id"], "reason": "null oracle"})
                continue  # verify-gate at generation: null oracle rejected
            c["_truth"] = vals
            verified.append(c)
            res.ok()
    finally:
        con.close()
    res.notes.append(f"verify-gate kept {len(verified)}/{len(cands)} "
                     "(null oracles rejected)")

    base = ctx.get("live_backend")
    if not base:
        for c in verified:
            res.skip(f"{c['id']}: unprobed without --live-backend")
            emit("question_asked", {"suite": "frontier", "qid": c["id"],
                                   "question": c["question"],
                                   "difficulty": c["difficulty"],
                                   "status": "unprobed"})
        emit("suite_finished", {"suite": "frontier", "mode": res.mode,
                                "passed": res.passed, "failed": res.failed,
                                "skipped": res.skipped})
        return res

    res.mode = "live-backend"
    res.ledger = "signal"
    # Verify BEFORE probing: the backend must serve the fixture this
    # suite's ground truth was computed from. (Keep the candidate list
    # intact: verify_warehouse returns a bool status, not candidates.)
    warehouse_ok, detail, _identity = client.verify_warehouse(
        base, fixture_sha)
    if not warehouse_ok:
        res.mode = "live-backend-unverified"
        for c in verified:
            res.fail(c["id"], f"warehouse-unverified: {detail}")
        res.notes.append("INVALID: no candidate was probed — the backend's "
                         "warehouse identity could not be verified against "
                         "the grading fixture. Generation verify-gates above "
                         "are hermetic and stand; only the live probing is "
                         "invalid.")
        emit("warehouse_unverified", {"suite": "frontier",
                                      "detail": detail[:300]})
        emit("suite_finished", {"suite": "frontier", "mode": res.mode,
                                "passed": res.passed, "failed": res.failed,
                                "skipped": res.skipped})
        return res
    res.notes.append(f"warehouse verified: {detail}")
    ask = client.ask
    retained = json.loads(RETAINED.read_text()) if RETAINED.is_file() else []
    kept_ids = {r["id"] for r in retained}
    misses = 0
    for c in verified:
        flat = [x for row in
                (c["_truth"] if c["expect"].get("multi_row") else [c["_truth"]])
                for x in row]
        exp = {"season": c["expect"].get("season"), "numbers": [],
               "names": []}
        for i in c["expect"].get("numbers_from", []):
            exp["numbers"].append(round(float(flat[i]), 2))
        for i in c["expect"].get("names_from", []):
            exp["names"].append(str(flat[i]))
        try:
            ans = ask(base, c["question"])
        except Exception as exc:
            res.fail(c["id"], f"backend ask failed: {exc}")
            continue
        ok, detail = scoring.check_answer(exp, ans["text"])
        emit("frontier_probed",
             {"qid": c["id"], "difficulty": c["difficulty"],
              "pass_bool": ok, "seconds": ans["seconds"],
              "tool_calls": ans["tool_calls"]})
        if ok:
            res.ok()
        else:
            misses += 1
            res.fail(c["id"], f"pipeline missed ({detail[:120]}); retained",
                     expected=exp, got=ans["text"][:200])
            if c["id"] not in kept_ids:
                rec = {k: v for k, v in c.items() if not k.startswith("_")}
                rec["retained_from"] = "frontier-gen1"
                retained.append(rec)
                kept_ids.add(c["id"])
            emit("frontier_retained", {"qid": c["id"], "detail": detail})
    RETAINED.write_text(json.dumps(retained, indent=2))
    res.notes.append(f"probed {len(verified)} against {base}; "
                     f"{misses} misses retained -> {RETAINED.name} "
                     f"({len(retained)} total protected)")
    emit("suite_finished", {"suite": "frontier", "mode": res.mode,
                            "passed": res.passed, "failed": res.failed,
                            "skipped": res.skipped})
    return res
