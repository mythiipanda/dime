"""Suite: golden warehouse questions (adopt 1: warehouse-grounded synthetic
question factory, CodeMidas/Skill2Env verify-gate).

Builds a small synthetic DuckDB warehouse (invented teams/players/seasons,
so no answer can come from pretraining), then for every runnable golden
question:
  1. runs the hidden verifier SQL -> truth values (computed, never typed);
  2. verify-gate: oracle returns non-null; an empty answer fails the
     check; a fabricated correct answer passes; a fabricated wrong-number
     answer fails; a fabricated wrong-season answer fails via the gate.

Stubbed questions (waiting on the DATA crew's backfill) and
real-warehouse questions (need --warehouse) are reported, never run.
Mode: hermetic (fixture) / skipped (real-warehouse without a file).
"""

from __future__ import annotations

import json
import random
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from suites import SuiteResult  # noqa: E402
import scoring  # noqa: E402
from trace import emit  # noqa: E402

import duckdb

DATA = Path(__file__).resolve().parent.parent / "data"
SEED = 7

TEAMS = {
    "ARC": ("Arcadia Arcs", ["Zane Mercer", "Theo Lindqvist"]),
    "BRV": ("Briar Vales", ["Milo Kessler", "Ren Okafor"]),
    "CRD": ("Coral Dunes", ["Jax Perrin", "Silas Vane"]),
    "DSK": ("Dusk Harbor", ["Eli Navarro", "Cade Hollis"]),
}
SEASONS = ["2023-24", "2024-25"]
BASE = {"ARC": 18, "BRV": 16, "CRD": 15, "DSK": 14}  # base pts per player


def build_fixture(path: Path):
    """Deterministic synthetic warehouse. Fixed seed; truth always via SQL."""
    rng = random.Random(SEED)
    con = duckdb.connect(str(path))
    con.execute("""
        CREATE TABLE silver_hist_gamelogs(
            player_name VARCHAR, team_abbreviation VARCHAR,
            game_date DATE, matchup VARCHAR, wl VARCHAR,
            pts DOUBLE, reb DOUBLE, ast DOUBLE,
            fgm DOUBLE, fga DOUBLE, fg3m DOUBLE, fg3a DOUBLE,
            ftm DOUBLE, fta DOUBLE, min DOUBLE,
            team_pts DOUBLE, opp_pts DOUBLE,
            _source VARCHAR, _season VARCHAR, _fetched_at VARCHAR)
    """)
    rows = []
    gid = 0
    abbrs = list(TEAMS)
    for si, season in enumerate(SEASONS):
        start = f"{2023 + si}-10-22"
        pair_idx = 0
        for i, a in enumerate(abbrs):
            for j, b in enumerate(abbrs):
                if j <= i:
                    continue
                for leg in (0, 1):  # home/away
                    home, away = (a, b) if leg == 0 else (b, a)
                    gid += 1
                    pair_idx += 1
                    # deterministic winner: home wins unless upset slot
                    upset = (pair_idx + si) % 3 == 0
                    winner = away if upset else home
                    for team in (home, away):
                        wl = "W" if team == winner else "L"
                        tpts = 0.0
                        prow = []
                        for pi, player in enumerate(TEAMS[team][1]):
                            pts = BASE[team] + rng.randint(-6, 10) + pi * 2
                            reb = rng.randint(2, 11)
                            ast = rng.randint(1, 9)
                            fgm = pts // 2.4
                            fga = fgm + rng.randint(4, 9)
                            fg3m = rng.randint(0, 4)
                            fg3a = fg3m + rng.randint(1, 5)
                            ftm = max(0, pts - 2 * fgm - fg3m)
                            fta = ftm + rng.randint(0, 3)
                            mins = 24 + rng.randint(0, 14)
                            tpts += pts
                            prow.append((player, pts, reb, ast, fgm, fga,
                                         fg3m, fg3a, ftm, fta, mins))
                        team_pts = tpts + 58  # bench scoring
                        for (player, pts, reb, ast, fgm, fga,
                             fg3m, fg3a, ftm, fta, mins) in prow:
                            opp = away if team == home else home
                            rows.append((
                                player, team,
                                f"{2023 + si}-10-{22 + (pair_idx % 9):02d}",
                                f"{team} vs. {opp}" if team == home
                                else f"{team} at {opp}",
                                wl, float(pts), float(reb), float(ast),
                                float(fgm), float(fga), float(fg3m),
                                float(fg3a), float(ftm), float(fta),
                                float(mins), float(team_pts),
                                float(team_pts - 8 if wl == "W"
                                      else team_pts + 6),
                                "synthetic-evals", season,
                                "2026-09-28T00:00:00Z"))
    con.executemany(
        "INSERT INTO silver_hist_gamelogs VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.close()
    return len(rows)


def _verifier_values(con, q):
    cur = con.execute(q["verifier_sql"])
    rows = cur.fetchall()
    if q.get("multi_row"):
        return [tuple(r) for r in rows]
    if not rows or rows[0][0] is None:
        return None
    return list(rows[0])


def _flatten(values, multi_row):
    if multi_row:
        return [c for row in values for c in row]
    return list(values)


def _fill(template, flat):
    if template is None:
        return None
    out = template
    for i, v in enumerate(flat):
        sv = round(float(v), 2) if isinstance(v, float) else str(v)
        out = out.replace("{%d}" % i, str(sv))
    return out


def _perturb_flat(flat, pos):
    vals = list(flat)
    v = vals[pos]
    vals[pos] = round(float(v) + 3.7, 2) if isinstance(v, float) else v + 2
    return vals


def run(ctx):
    res = SuiteResult(name="golden_warehouse", mode="hermetic")
    emit("suite_started", {"suite": "golden_warehouse", "mode": "hermetic"})
    questions = json.loads((DATA / "golden_questions.json").read_text())[
        "questions"]

    tmp = Path(tempfile.mkdtemp(prefix="evals-wh-"))
    db = tmp / "fixture.duckdb"
    try:
        nrows = build_fixture(db)
    except Exception as exc:
        res.fail("fixture-build", f"could not build fixture: {exc}")
        return res

    con = duckdb.connect(str(db), read_only=True)
    try:
        # fixture integrity: provenance on every row, expected shape
        prov = con.execute(
            "SELECT COUNT(*) FROM silver_hist_gamelogs "
            "WHERE _source IS NULL OR _season IS NULL "
            "OR _fetched_at IS NULL").fetchone()[0]
        if prov:
            res.fail("fixture-provenance",
                     f"{prov} rows missing provenance columns")
        else:
            res.ok()
        seasons = sorted(r[0] for r in con.execute(
            "SELECT DISTINCT _season FROM silver_hist_gamelogs").fetchall())
        if seasons != SEASONS:
            res.fail("fixture-seasons", f"seasons {seasons} != {SEASONS}")
        else:
            res.ok()
    except Exception as exc:
        res.fail("fixture-integrity", str(exc))
        con.close()
        return res

    for q in questions:
        qid = q["id"]
        if q.get("status") == "stubbed":
            res.skip(f"{qid} stubbed; needs {q['needs']}")
            emit("question_asked", {"suite": "golden_warehouse", "qid": qid,
                                   "question": q["question"],
                                   "generation": q.get("generation"),
                                   "status": "stubbed"})
            continue
        if q.get("warehouse") == "real":
            res.skip(f"{qid} needs --warehouse with a real warehouse file")
            continue
        emit("question_asked", {"suite": "golden_warehouse", "qid": qid,
                               "question": q["question"],
                               "generation": q.get("generation")})
        try:
            values = _verifier_values(con, q)
        except Exception as exc:
            res.fail(qid, f"verifier SQL failed: {exc}")
            continue
        if values is None:
            res.fail(qid, "verify-gate: oracle query returned null/empty; "
                          "question rejected")
            continue

        # build expected from truth values (computed, never typed).
        # flat positions follow the verifier row order, matching the
        # {0}/{1} slots in the fabrication templates.
        flat = _flatten(values, q.get("multi_row"))
        exp = {"season": q["expect"].get("season"), "numbers": [], "names": []}
        for i in q["expect"].get("numbers_from", []):
            exp["numbers"].append(round(float(flat[i]), 2))
        for i in q["expect"].get("names_from", []):
            exp["names"].append(str(flat[i]))
        exp["names"].extend(q["expect"].get("names", []))

        fab = q.get("fabricate", {})
        # gate 1: empty answer fails (check is not vacuous)
        ok, detail = scoring.check_answer(exp, "")
        if ok:
            res.fail(qid, "verify-gate: empty answer passed the check; "
                          "check is vacuous")
            continue
        # gate 2: fabricated correct answer passes
        correct = _fill(fab.get("correct", ""), flat)
        ok, detail = scoring.check_answer(exp, correct)
        if not ok:
            res.fail(qid, f"verify-gate: fabricated correct answer failed: "
                          f"{detail}", expected=exp, got=correct)
            continue
        # gate 3: wrong number fails. Perturb EVERY expected number
        # position: leaving one true value in the answer would make the
        # check pass for the wrong reason.
        npos = q["expect"].get("numbers_from", [])
        pert = flat
        for p in npos:
            pert = _perturb_flat(pert, p)
        wrong = _fill(fab.get("wrong_number", ""), pert)
        ok, _ = scoring.check_answer(exp, wrong)
        if ok:
            res.fail(qid, "verify-gate: wrong-number answer passed; "
                          "check cannot discriminate")
            continue
        # gate 4: wrong season fails via the gate
        wt = fab.get("wrong_season")
        if wt:
            ok, _ = scoring.check_answer(exp, _fill(wt, flat))
            if ok:
                res.fail(qid, "verify-gate: wrong-season answer passed; "
                              "season gate not tripping")
                continue
        res.ok()
        emit("verdict", {"qid": qid, "criterion": "verify-gate",
                         "pass_bool": True,
                         "detail": f"truth={exp['numbers']}"})
    con.close()

    # real-warehouse questions run when a warehouse file is provided
    wh = ctx.get("warehouse")
    if wh and Path(wh).is_file():
        res.mode = "hermetic+live-warehouse"
        rcon = duckdb.connect(str(wh), read_only=True)
        try:
            tables = {r[0] for r in
                      rcon.execute("SHOW TABLES").fetchall()}
        except Exception:
            tables = set()
        for q in questions:
            if q.get("warehouse") != "real":
                continue
            qid = q["id"]
            if "silver_hist_gamelogs" not in tables:
                res.skip(f"{qid}: silver_hist_gamelogs absent from warehouse")
                continue
            try:
                values = _verifier_values(rcon, q)
            except Exception as exc:
                res.fail(qid, f"real-warehouse verifier failed: {exc}")
                continue
            if values is None:
                res.fail(qid, "real-warehouse oracle returned null")
                continue
            res.ok()
            emit("verdict", {"qid": qid, "criterion": "real-truth-computed",
                             "pass_bool": True})
        rcon.close()
    res.notes.append(f"fixture: {nrows} rows, seed={SEED}, "
                     f"invented teams {sorted(TEAMS)}")
    emit("suite_finished", {"suite": "golden_warehouse", "mode": res.mode,
                            "passed": res.passed, "failed": res.failed,
                            "skipped": res.skipped})
    return res
