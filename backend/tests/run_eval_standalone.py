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
     (AST-extracted; the hand-labeled qtype stands in for the LLM's
     entity-level intent via the question_kind kwarg, mirroring the
     production call path _gated_tables <- state["answer_entity_level"])

Global: no SKILL_KEYWORDS / match_skills in product code (static,
tokenize-aware).

What this runner measures: metadata/schema checks + synthetic gate
behavior. NOT measured here: response quality (correct numbers, real
rendered tables) -- that needs a live LLM + warehouse, out of scope.

Usage: python3 backend/tests/run_eval_standalone.py
Exit 0 if >= 18/20 pass, else 1.
"""

import ast
import os
import re
import sys
import tokenize

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

    Returns a namespace dict with the two functions. Callers pass explicit
    question_kind (the LLM's answer_entity_level in production), so no
    entity-detection stubbing is needed.
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
    ns = {"re": re}

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

# Production contract: the LLM's entity-level intent
# (state["answer_entity_level"]) drives the gate, not question-text
# keywords. The hand-labeled qtype stands in for that intent here.
QTYPE_KIND = {
    "player_compare": "player",
    "defensive_player": "player",
    "team_offense": "team",
    "team_stats": "team",
    "team_defense": "team",
}

def check_table_kind_gate(ns, prompt, qtype, players, teams):
    """Player q + team table -> reject; team q + player table -> reject.

    Passes the hand-labeled qtype as question_kind (the LLM's
    answer_entity_level in production). Entity-less team questions
    ("best offense this season?") are exercised here, not skipped:
    with explicit intent the gate must reject mismatched tables.
    """
    kind = QTYPE_KIND.get(qtype)
    if kind is None:
        return True, "n/a"
    fn = ns.get("verify_table_kind")
    if fn is None:
        return False, "verify_table_kind not extracted"
    try:
        if kind == "player":
            # player question + team table must be rejected (False)
            team_table = {"kind": "team", "rows": [{"TEAM": "BOS"}]}
            result = fn(prompt, team_table, question_kind="player")
            if result is not False:
                return False, f"player-q + team-table not rejected (got {result})"
        else:
            player_table = {"kind": "player", "rows": [{"PLAYER": "X"}]}
            result = fn(prompt, player_table, question_kind="team")
            if result is not False:
                return False, f"team-q + player-table not rejected (got {result})"
    except Exception as e:
        return False, f"gate crashed: {e}"
    return True, "ok"

def check_no_keyword_routing():
    """Flag real keyword-routing code via stdlib tokenize.

    COMMENT and STRING tokens are skipped entirely, so docstrings/comments
    mentioning match_skills never trip it. Scans every .py file under
    backend/ (including this runner and the eval data module — their
    mentions live in strings/docstrings, which tokenize ignores). Only
    __pycache__/node_modules dirs are skipped. Flags only real code tokens:
    NAME SKILL_KEYWORDS followed by OP "=" or ":"; NAME match_skills
    preceded by NAME "def"; NAME match_skills followed by OP "(" not
    preceded by OP ".".
    """
    offenders = []
    _SKIP = {
        tokenize.COMMENT, tokenize.STRING, tokenize.NL,
        tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
        tokenize.ENDMARKER, tokenize.ENCODING,
    }
    backend_dir = os.path.join(REPO, "backend")
    for root, _, files in os.walk(backend_dir):
        if "node_modules" in root or "__pycache__" in root:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(root, fn)
            try:
                with open(p, encoding="utf-8") as f:
                    toks = [t for t in tokenize.generate_tokens(f.readline)
                            if t.type not in _SKIP]
            except Exception:
                continue
            for i, tok in enumerate(toks):
                if tok.type != tokenize.NAME:
                    continue
                prev = toks[i - 1] if i > 0 else None
                nxt = toks[i + 1] if i + 1 < len(toks) else None
                if tok.string == "SKILL_KEYWORDS":
                    if nxt is not None and nxt.type == tokenize.OP \
                            and nxt.string in ("=", ":"):
                        offenders.append(f"{os.path.relpath(p, REPO)}:{tok.start[0]}")
                elif tok.string == "match_skills":
                    if prev is not None and prev.type == tokenize.NAME \
                            and prev.string == "def":
                        offenders.append(f"{os.path.relpath(p, REPO)}:{tok.start[0]}")
                    elif nxt is not None and nxt.type == tokenize.OP \
                            and nxt.string == "(":
                        if not (prev is not None
                                and prev.type == tokenize.OP
                                and prev.string == "."):
                            offenders.append(f"{os.path.relpath(p, REPO)}:{tok.start[0]}")
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

    # The eval is honest only when these stay separate:
    #   A. metadata/schema — "is the eval valid and the code the right shape?"
    #      (wellformed eval data, skill catalog integrity, no-keyword-routing
    #      static code identity)
    #   B. response-quality proxies — "do the guards behave on representative
    #      answers?" (minutes-qual gate, table-kind gate)
    # Section B passing says nothing about section A, and vice versa.
    results = []
    for i, (prompt, qtype, skills, players, teams) in enumerate(cases):
        pid = f"p{i+1:02d}"
        meta = []
        ok1, m1 = check_wellformed(prompt, qtype, skills, players, teams, known_skills)
        meta.append(("wellformed", ok1, m1))
        ok2, m2 = check_skills_exist(skills)
        meta.append(("skills-exist", ok2, m2))
        quality = []
        ok3, m3 = check_minutes_gate(ns, qtype)
        quality.append(("minutes-gate", ok3, m3))
        ok4, m4 = check_table_kind_gate(ns, prompt, qtype, players, teams)
        quality.append(("table-kind-gate", ok4, m4))
        results.append((pid, prompt, qtype, meta, quality))

    ok_kw, m_kw = check_no_keyword_routing()
    meta_pass = sum(1 for _, _, _, m, _ in results if all(ok for _, ok, _ in m))
    qual_pass = sum(1 for _, _, _, _, q in results if all(ok for _, ok, _ in q))

    print(f"\n== A. metadata/schema (target: {len(results)}/{len(results)} "
          f"+ global static check) ==")
    print(f"Global static check (no keyword routing): {'PASS' if ok_kw else 'FAIL'} {m_kw}")
    print(f"Per-case metadata checks: {meta_pass}/{len(results)} pass")
    for pid, prompt, qtype, meta, _ in results:
        if not all(ok for _, ok, _ in meta):
            short = (prompt[:52] + "..") if len(prompt) > 54 else prompt
            print(f"  {pid} [{qtype}] FAIL {short}")
            for name, ok, msg in meta:
                if not ok:
                    cls = ("eval-data issue" if name == "wellformed"
                           else "data issue (missing skill file)")
                    print(f"    - [{name}] {msg} — classification: {cls}")

    print(f"\n== B. response-quality proxies (target: 18/20 = 90%) ==")
    print(f"{'ID':<5} {'QTYPE':<16} {'PASS':<6} PROMPT")
    for pid, prompt, qtype, _, quality in results:
        passed = all(ok for _, ok, _ in quality)
        short = (prompt[:52] + "..") if len(prompt) > 54 else prompt
        print(f"{pid:<5} {qtype:<16} {'PASS' if passed else 'FAIL':<6} {short}")
        if not passed:
            for name, ok, msg in quality:
                if not ok:
                    cls = ("guard issue (minutes-qual gate)" if name == "minutes-gate"
                           else "guard issue (table-kind gate)")
                    print(f"       - [{name}] {msg}")
                    print(f"         classification: {cls}")

    print(f"\n==== RESULT A (metadata): {meta_pass}/{len(results)} "
          f"({'PASS' if meta_pass == len(results) and ok_kw else 'FAIL'}) ====")
    print(f"==== RESULT B (response quality): {qual_pass}/{len(results)} "
          f"({100.0*qual_pass/len(results):.0f}%) "
          f"{'TARGET MET' if qual_pass >= 18 else 'TARGET NOT MET'} ====")
    return 0 if (meta_pass == len(results) and ok_kw and qual_pass >= 18) else 1

if __name__ == "__main__":
    sys.exit(main())
