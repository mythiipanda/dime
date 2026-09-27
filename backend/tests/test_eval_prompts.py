"""
Phase 4 eval: 20 real prompts from Tony's usage, structural validation.

Each case: prompt + expected question type + expected v2 skills + expected entities.

What this file measures:
  (a) metadata/schema checks (wellformed, skills-exist, no-keyword-routing),
  (b) synthetic gate-behavior checks (hand-built tables, no LLM),
  (c) NOT measured here: response quality (correct numbers, real tables) --
      needs a live LLM + warehouse, out of scope for this file.

Run in CI with pytest. In sandbox (no deps), use the standalone runner:
  python3 backend/tests/run_eval_standalone.py
"""

import pytest

# ---------------------------------------------------------------------------
# Eval cases: (prompt, qtype, expected_skills, expected_players, expected_teams)
# qtype: player_compare | defensive_league | defensive_player | followup |
#        team_offense | team_defense | leaderboard | season_leader | team_stats
# ---------------------------------------------------------------------------

EVAL_CASES = [
    # --- Browser QA (Tony's real prompts) ---
    (
        "Compare Luka Don\u010di\u0107 and Shai Gilgeous-Alexander",
        "player_compare",
        ["player-comparison"],
        ["Luka Don\u010di\u0107", "Shai Gilgeous-Alexander"],
        [],
    ),
    (
        "best defensive players?",
        "defensive_league",
        ["defensive-analysis"],
        [],
        [],
    ),
    (
        "no i mean best defensive players in the league",
        "followup",
        ["defensive-analysis", "followup-correction"],
        [],
        [],
    ),
    # --- Termination gate regressions ---
    (
        "best offense this season?",
        "team_offense",
        ["team-offense"],
        [],
        [],
    ),
    (
        "which team has the best offense?",
        "team_offense",
        ["team-offense"],
        [],
        [],
    ),
    # --- Season resolution ---
    (
        "Who had the highest true shooting percentage in the 2024-25 season (min 1000 minutes)?",
        "season_leader",
        ["leaderboard"],
        [],
        [],
    ),
    # --- Team resolution ---
    (
        "boston celtics stats",
        "team_stats",
        ["team-offense"],
        [],
        ["Boston Celtics"],
    ),
    # --- Leaderboard + minutes qual ---
    (
        "who leads the league in steals?",
        "leaderboard",
        ["leaderboard"],
        [],
        [],
    ),
    # --- Defensive analysis (single player) ---
    (
        "is jayson tatum a good defender?",
        "defensive_player",
        ["defensive-analysis"],
        ["Jayson Tatum"],
        [],
    ),
    # --- Team comparison ---
    (
        "lakers vs celtics who has better offense?",
        "team_offense",
        ["team-offense"],
        [],
        ["Lakers", "Celtics"],
    ),
    # --- Additional 10: common basketball patterns ---
    (
        "Compare Jayson Tatum and Jaylen Brown's efficiency this season",
        "player_compare",
        ["player-comparison"],
        ["Jayson Tatum", "Jaylen Brown"],
        [],
    ),
    (
        "which team has the best defense?",
        "team_defense",
        ["defensive-analysis"],
        [],
        [],
    ),
    (
        "who has the most blocks per game (min 500 minutes)?",
        "leaderboard",
        ["leaderboard"],
        [],
        [],
    ),
    (
        "actually I meant the lakers",
        "followup",
        ["followup-correction"],
        [],
        ["Lakers"],
    ),
    (
        "Who leads the league in three-point percentage?",
        "leaderboard",
        ["leaderboard"],
        [],
        [],
    ),
    (
        "Is Victor Wembanyama the best defender in the league?",
        "defensive_player",
        ["defensive-analysis"],
        ["Victor Wembanyama"],
        [],
    ),
    (
        "warriors team stats this season",
        "team_stats",
        ["team-offense"],
        [],
        ["Warriors"],
    ),
    (
        "Compare the Celtics and Thunder defenses",
        "team_defense",
        ["defensive-analysis"],
        [],
        ["Celtics", "Thunder"],
    ),
    (
        "Who had the highest PER in 2023-24?",
        "season_leader",
        ["leaderboard"],
        [],
        [],
    ),
    (
        "no, I meant best offensive players in the league",
        "followup",
        ["leaderboard", "followup-correction"],
        [],
        [],
    ),
]

# All skills referenced by eval cases must exist in backend/v2/skills/
EXPECTED_SKILLS = {
    "defensive-analysis",
    "player-comparison",
    "team-offense",
    "leaderboard",
    "followup-correction",
}


def _skills_dir():
    import os
    return os.path.join(os.path.dirname(__file__), "..", "v2", "skills")


@pytest.mark.parametrize(
    "prompt,qtype,expected_skills,expected_players,expected_teams",
    EVAL_CASES,
    ids=[f"p{i+1:02d}" for i in range(len(EVAL_CASES))],
)
def test_eval_prompt_wellformed(prompt, qtype, expected_skills,
                                expected_players, expected_teams):
    """Structural: prompt is non-empty, qtype is known, skills are known."""
    assert isinstance(prompt, str) and len(prompt.strip()) >= 3, \
        f"prompt too short: {prompt!r}"
    assert qtype in {
        "player_compare", "defensive_league", "defensive_player",
        "followup", "team_offense", "team_defense",
        "leaderboard", "season_leader", "team_stats",
    }, f"unknown qtype: {qtype}"
    for skill in expected_skills:
        assert skill in EXPECTED_SKILLS, f"unknown skill: {skill}"


@pytest.mark.parametrize(
    "prompt,qtype,expected_skills,expected_players,expected_teams",
    EVAL_CASES,
    ids=[f"p{i+1:02d}" for i in range(len(EVAL_CASES))],
)
def test_eval_expected_skills_exist(prompt, qtype, expected_skills,
                                   expected_players, expected_teams):
    """Structural: every expected skill has a v2 SKILL.md on disk."""
    import os
    for skill in expected_skills:
        path = os.path.join(_skills_dir(), skill, "SKILL.md")
        assert os.path.isfile(path), f"missing skill file: {path}"


def test_eval_no_keyword_routing():
    """Structural (static): no exact-substring keyword routing on question text.

    Tokenize-aware: stdlib `tokenize` skips COMMENT and STRING tokens
    entirely, so docstrings/comments mentioning match_skills never trip it.
    Flags only real code tokens:
      (a) NAME SKILL_KEYWORDS followed by OP "=" or OP ":",
      (b) NAME match_skills preceded by NAME "def",
      (c) NAME match_skills followed by OP "(" not preceded by OP ".".
    """
    import os
    import tokenize
    backend = os.path.join(os.path.dirname(__file__), "..")
    offenders = []
    _SKIP = {
        tokenize.COMMENT, tokenize.STRING, tokenize.NL,
        tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
        tokenize.ENDMARKER, tokenize.ENCODING,
    }
    for root, _, files in os.walk(backend):
        if "node_modules" in root or "__pycache__" in root:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(root, fn)
            if "test_eval_prompts" in p:
                continue
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
                        offenders.append(f"{p}:{tok.start[0]}")
                elif tok.string == "match_skills":
                    if prev is not None and prev.type == tokenize.NAME \
                            and prev.string == "def":
                        offenders.append(f"{p}:{tok.start[0]}")
                    elif nxt is not None and nxt.type == tokenize.OP \
                            and nxt.string == "(":
                        if not (prev is not None
                                and prev.type == tokenize.OP
                                and prev.string == "."):
                            offenders.append(f"{p}:{tok.start[0]}")
    assert not offenders, f"keyword routing found in: {offenders}"


# ---------------------------------------------------------------------------
# Gate function structural tests (synthetic inputs, no LLM)
# These import from backend.app.graph when deps are available (CI).
# In the sandbox they are exercised via AST extraction in run_eval_standalone.py.
# ---------------------------------------------------------------------------

try:
    from app.graph import (
        verify_table_kind,
        verify_minutes_qual,
        verify_numbers_traced,
    )
    _GATES_IMPORTABLE = True
except Exception:
    _GATES_IMPORTABLE = False

pytestmark_gates = pytest.mark.skipif(
    not _GATES_IMPORTABLE, reason="backend.app.graph not importable (no deps)")

# Production contract: the LLM's intent (state["answer_entity_level"]),
# not question-text keywords or entity stubbing, drives the gate.
# The tests below pass that intent explicitly via question_kind=.


@pytest.mark.parametrize("prompt,qtype,expected_skills,expected_players,expected_teams",
                         [c for c in EVAL_CASES if c[1] in ("player_compare", "defensive_player")],
                         ids=[f"p{i+1:02d}" for i, c in enumerate(EVAL_CASES)
                              if c[1] in ("player_compare", "defensive_player")])
@pytestmark_gates
def test_eval_player_question_rejects_team_table(prompt, qtype, expected_skills,
                                                 expected_players, expected_teams):
    """Gate: player question + team-kind table -> reject (False)."""
    team_table = {"kind": "team", "rows": [{"TEAM": "BOS", "ORTG": 120.5}]}
    assert verify_table_kind(prompt, team_table, question_kind="player") is False


@pytest.mark.parametrize("prompt,qtype,expected_skills,expected_players,expected_teams",
                         [c for c in EVAL_CASES if c[1] in ("team_offense", "team_stats", "team_defense")],
                         ids=[f"p{i+1:02d}" for i, c in enumerate(EVAL_CASES)
                              if c[1] in ("team_offense", "team_stats", "team_defense")])
@pytestmark_gates
def test_eval_team_question_rejects_player_table(prompt, qtype, expected_skills,
                                                 expected_players, expected_teams):
    """Gate: team question + player-kind table -> reject (False)."""
    player_table = {"kind": "player", "rows": [{"PLAYER": "Jayson Tatum", "PPG": 30.1}]}
    assert verify_table_kind(prompt, player_table, question_kind="team") is False


@pytest.mark.parametrize("prompt,qtype,expected_skills,expected_players,expected_teams",
                         [c for c in EVAL_CASES if c[1] in ("leaderboard", "season_leader")],
                         ids=[f"p{i+1:02d}" for i, c in enumerate(EVAL_CASES)
                              if c[1] in ("leaderboard", "season_leader")])
@pytestmark_gates
def test_eval_leaderboard_requires_minutes_qual(prompt, qtype, expected_skills,
                                                expected_players, expected_teams):
    """Gate: rate-stat claim without minutes qual -> flagged."""
    answer = "He leads the league in steals with 2.1 SPG."
    violations = verify_minutes_qual(answer, [])
    assert len(violations) > 0, f"expected minutes-qual violation for: {prompt!r}"
    answer_ok = "He leads the league in steals with 2.1 SPG (min 500 minutes)."
    assert verify_minutes_qual(answer_ok, []) == []
