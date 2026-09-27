#!/usr/bin/env python3
"""
Phase 4 eval standalone runner (sandbox: no pytest, no langchain_core).

Loads EVAL_CASES from test_eval_prompts.py via AST, then runs structural
checks per prompt:
  1. Prompt well-formed (non-empty, known qtype, known skills)
  2. Expected v2 skill SKILL.md files exist on disk
  3. Gate: verify_minutes_qual flags unqualified rate-stat claims
     (AST-extracted from backend/app/graph.py with regex constants)
  4. Gate: verify_table_kind rejects kind-mismatched tables
     (AST-extracted; _detect_entities stubbed from eval-case metadata)

Global: no SKILL_KEYWORDS / match_skills in codebase (static).

Usage: python3 backend/tests/run_eval_standalone.py
Exit 0 if >= 18/20 pass, else 1.
"""

import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
REPO = os.path.dirname(BACKEND)

# ---------------------------------------------------------------------------
# 1. Load EVAL_CASES via AST (don't import the test module — it needs pytest)
# ---------------------------------------------------------------------------

def load_eval_cases():
    path = os.path.join(HERE, "test_eval_prompts.py")
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "EVAL_CASES":
                    return ast.literal_eval(node.value)
    raise RuntimeError("EVAL_CASES not found")

def load_expected_skills():
    path = os.path.join(HERE, "test_eval_prompts.py")
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "EXPECTED_SKILLS":
                    return set(ast.literal_eval(node.value))
    raise RuntimeError("EXPECTED_SKILLS not found")

KNOWN_QTYPES = {
    "player_compare", "defensive_league", "defensive_player",
    "followup", "team_offense", "team_defense",
    "leaderboard", "season_leader", "team_stats",
}

# ---------------------------------------------------------------------------
# 2. AST-extract gate functions from backend/app/graph.py
# ---------------------------------------------------------------------------

def extract_gate_helpers():
    """Extract verify_minutes_qual + verify_table_kind with deps via AST.

    Returns a namespace dict with the two functions, stubbing _detect_entities
    (caller must set STUB_ENTITIES before calling verify_table_kind).
    """
    path = os.path.join(BACKEND, "app", "graph.py")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src)

    wanted_funcs = {
        "verify_minutes_qual", "verify_table_kind",
        "_gate_question_kind", "_gate_table_level", "_iter_units",
    }
    # Regex constants are module-level assignments; grab by name prefix.
    wanted_consts = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and (
                    t.id.startswith("_MINUTES_") or t.id == "_GATE_TEAM_TABLE_RX"
                    or t.id == "_UNIT_SPLIT_RX"
                ):
                    wanted_consts.add(t.id)

    mod = ast.Module(body=[], type_ignores=[])
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted_funcs:
            mod.body.append(node)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in wanted_consts:
                    mod.body.append(node)
    # _iter_units may be async or need helpers; check what it uses.
    ns = {"re": re, "STUB_ENTITIES": ([], [])}

    stub = (
        "def _detect_entities(question):\n"
        "    return STUB_ENTITIES\n"
    )
    code = compile(ast.parse(stub), "<stub>", "exec")
    exec(code, ns)

    code = compile(mod, "<gate_extract>", "exec")
    exec(code, ns)
    return ns

# ---------------------------------------------------------------------------
# 3. Per-prompt checks
# ---------------------------------------------------------------------------

def check_wellformed(prompt, qtype, skills, players, teams, known_skills):
    if not isinstance(prompt, str) or len(prompt.strip()) < 3:
        return False, "prompt too short"
    if qtype not in KNOWN_QTYPES:
        return False, f"unknown qtype {qtype}"
    for s in skills:
        if s not in known_skills:
            return False, f"unknown skill {s}"
    return True, "ok"

def check_skills_exist(skills):
    missing = []
    for s in skills:
        p = os.path.join(REPO, "backend", "v2", "skills", s, "SKILL.md")
        if not os.path.isfile(p):
            missing.append(s)
    if missing:
        return False, f"missing SKILL.md: {missing}"
    return True, "ok"

def check_minutes_gate(ns, qtype):
    """Leaderboard prompts: unqualified rate-stat claim must be flagged."""
    if qtype not in ("leaderboard", "season_leader"):
        return True, "n/a"
    fn = ns.get("verify_minutes_qual")
    if fn is None:
        return False, "verify_minutes_qual not extracted"
    bad = "He leads the league in steals with 2.1 SPG."
    good = "He leads the league in steals with 2.1 SPG (min 500 minutes)."
    try:
        v_bad = fn(bad, [])
        v_good = fn(good, [])
    except Exception as e:
        return False, f"gate crashed: {e}"
    if not v_bad:
        return False, "unqualified claim NOT flagged"
    if v_good:
        return False, "qualified claim wrongly flagged"
    return True, "ok"

def check_table_kind_gate(ns, prompt, qtype, players, teams):
    """Player q + team table -> reject; team q + player table -> reject.

    Only applies when entities are present. Entity-less questions
    ("best offense this season?") yield kind "other" by design — the gate
    is permissive there, so those cases are n/a.
    """
    if qtype not in ("player_compare", "defensive_player",
                     "team_offense", "team_stats", "team_defense"):
        return True, "n/a"
    if not players and not teams:
        return True, "n/a (no entities -> kind 'other' by design)"
    fn = ns.get("verify_table_kind")
    if fn is None:
        return False, "verify_table_kind not extracted"
    ns["STUB_ENTITIES"] = (players, teams)
    try:
        if qtype in ("player_compare", "defensive_player"):
            # player question + team table must be rejected (False)
            team_table = {"kind": "team", "rows": [{"TEAM": "BOS"}]}
            result = fn(prompt, team_table)
            if result is not False:
                return False, f"player-q + team-table not rejected (got {result})"
        else:
            player_table = {"kind": "player", "rows": [{"PLAYER": "X"}]}
            result = fn(prompt, player_table)
            if result is not False:
                return False, f"team-q + player-table not rejected (got {result})"
    except Exception as e:
        return False, f"gate crashed: {e}"
    return True, "ok"

def check_no_keyword_routing():
    """Flag real keyword-routing code, not tests asserting its absence.

    Flags: SKILL_KEYWORDS assignment, `def match_skills`, or match_skills()
    calls outside of negative assertions (assert not hasattr / "are gone").
    """
    offenders = []
    for root, _, files in os.walk(os.path.join(REPO, "backend")):
        if "__pycache__" in root:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(root, fn)
            if "test_eval_prompts" in p or "run_eval_standalone" in p:
                continue
            try:
                with open(p, encoding="utf-8") as f:
                    lines = f.readlines()
            except OSError:
                continue
            for i, line in enumerate(lines, 1):
                s = line.strip()
                # Skip comments/docstrings mentioning removal
                if s.startswith("#") or s.startswith('"""') or s.startswith("'''"):
                    if "gone" in s.lower() or "remov" in s.lower():
                        continue
                if re.search(r"\bSKILL_KEYWORDS\s*=", line):
                    offenders.append(f"{os.path.relpath(p, REPO)}:{i}")
                elif re.search(r"def\s+match_skills\s*\(", line):
                    offenders.append(f"{os.path.relpath(p, REPO)}:{i}")
                elif re.search(r"(?<![\w.])match_skills\s*\(", line):
                    # Allow negative assertions verifying absence
                    if "not hasattr" not in line and "gone" not in line.lower():
                        offenders.append(f"{os.path.relpath(p, REPO)}:{i}")
    if offenders:
        return False, f"keyword routing in: {offenders}"
    return True, "ok"

# ---------------------------------------------------------------------------
# 4. Main
# ---------------------------------------------------------------------------

def main():
    cases = load_eval_cases()
    known_skills = load_expected_skills()
    print(f"Loaded {len(cases)} eval cases.")
    try:
        ns = extract_gate_helpers()
        print("Gate functions extracted OK.")
    except Exception as e:
        print(f"Gate extraction FAILED: {e}")
        ns = {}

    results = []
    for i, (prompt, qtype, skills, players, teams) in enumerate(cases):
        pid = f"p{i+1:02d}"
        checks = []
        ok1, m1 = check_wellformed(prompt, qtype, skills, players, teams, known_skills)
        checks.append(("wellformed", ok1, m1))
        ok2, m2 = check_skills_exist(skills)
        checks.append(("skills-exist", ok2, m2))
        ok3, m3 = check_minutes_gate(ns, qtype)
        checks.append(("minutes-gate", ok3, m3))
        ok4, m4 = check_table_kind_gate(ns, prompt, qtype, players, teams)
        checks.append(("table-kind-gate", ok4, m4))
        passed = all(ok for _, ok, _ in checks)
        results.append((pid, prompt, qtype, passed, checks))

    ok_kw, m_kw = check_no_keyword_routing()
    print(f"\nGlobal static check (no keyword routing): {'PASS' if ok_kw else 'FAIL'} {m_kw}")

    npass = sum(1 for _, _, _, p, _ in results if p)
    print(f"\n{'ID':<5} {'QTYPE':<16} {'PASS':<6} PROMPT")
    for pid, prompt, qtype, passed, checks in results:
        mark = "PASS" if passed else "FAIL"
        short = (prompt[:52] + "..") if len(prompt) > 54 else prompt
        print(f"{pid:<5} {qtype:<16} {mark:<6} {short}")
        if not passed:
            for name, ok, msg in checks:
                if not ok:
                    print(f"       - [{name}] {msg}")
                    # classify
                    if name == "skills-exist":
                        print("         classification: data issue (missing skill file)")
                    elif name == "minutes-gate":
                        print("         classification: guard issue (minutes-qual gate)")
                    elif name == "table-kind-gate":
                        print("         classification: guard issue (table-kind gate)")
                    elif name == "wellformed":
                        print("         classification: eval-data issue")

    print(f"\n==== RESULT: {npass}/{len(results)} pass "
          f"({100.0*npass/len(results):.0f}%) ====")
    if not ok_kw:
        print("NOTE: global keyword-routing check FAILED (counts separately).")
    target = 18
    print(f"Target: {target}/20 (90%). {'MET' if npass >= target and ok_kw else 'NOT MET'}")
    return 0 if (npass >= target and ok_kw) else 1

if __name__ == "__main__":
    sys.exit(main())
