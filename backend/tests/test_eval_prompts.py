"""
Phase 4 eval: 20 real prompts from Tony's usage, structural validation.

Each case: prompt + expected question type + expected v2 skills + expected entities.
Structural checks (no live LLM calls):
  1. Expected skills exist in backend/v2/skills/
  2. Prompt builds a valid planner prompt (v1) / TaskSpec (v2) without crashing
  3. Termination gate functions accept/reject synthetic outputs correctly
  4. No keyword routing in codebase (static check, one test)

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

    Flags real code (SKILL_KEYWORDS assignment, def/call of match_skills),
    not tests asserting their absence.
    """
    import os
    import re
    backend = os.path.join(os.path.dirname(__file__), "..")
    offenders = []
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
                    lines = f.readlines()
            except OSError:
                continue
            for i, line in enumerate(lines, 1):
                s = line.strip()
                if s.startswith("#") and ("gone" in s.lower() or "remov" in s.lower()):
                    continue
                if re.search(r"\bSKILL_KEYWORDS\s*=", line):
                    offenders.append(f"{p}:{i}")
                elif re.search(r"def\s+match_skills\s*\(", line):
                    offenders.append(f"{p}:{i}")
                elif re.search(r"(?<![\w.])match_skills\s*\(", line):
                    if "not hasattr" not in line and "gone" not in line.lower():
                        offenders.append(f"{p}:{i}")
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


@pytest.mark.parametrize("prompt,qtype,expected_skills,expected_players,expected_teams",
                         [c for c in EVAL_CASES if c[1] in ("player_compare", "defensive_player")],
                         ids=[f"p{i+1:02d}" for i, c in enumerate(EVAL_CASES)
                              if c[1] in ("player_compare", "defensive_player")])
@pytestmark_gates
def test_eval_player_question_rejects_team_table(prompt, qtype, expected_skills,
                                                 expected_players, expected_teams):
    """Gate: player question + team-kind table -> reject (False)."""
    team_table = {"kind": "team", "rows": [{"TEAM": "BOS", "ORTG": 120.5}]}
    assert verify_table_kind(prompt, team_table) is False


@pytest.mark.parametrize("prompt,qtype,expected_skills,expected_players,expected_teams",
                         [c for c in EVAL_CASES if c[1] in ("team_offense", "team_stats", "team_defense")],
                         ids=[f"p{i+1:02d}" for i, c in enumerate(EVAL_CASES)
                              if c[1] in ("team_offense", "team_stats", "team_defense")])
@pytestmark_gates
def test_eval_team_question_rejects_player_table(prompt, qtype, expected_skills,
                                                 expected_players, expected_teams):
    """Gate: team question + player-kind table -> reject (False)."""
    player_table = {"kind": "player", "rows": [{"PLAYER": "Jayson Tatum", "PPG": 30.1}]}
    assert verify_table_kind(prompt, player_table) is False


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
