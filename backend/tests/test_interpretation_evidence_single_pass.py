from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "backend/analyst/skills/interpretation-and-evidence/SKILL.md"


def test_interpretation_skill_teaches_single_pass_aggregation():
    src = SKILL.read_text(encoding="utf-8")
    assert "Prefer single-pass aggregation: one `sql_exec`" in src
    for phrase in (
        "GROUP BY",
        "conditional aggregation",
        "window functions",
        "small CTE chain",
        "Round trips are the exception",
        "not as a loop over teams or players",
    ):
        assert phrase in src


def test_interpretation_skill_pins_two_before_after_examples():
    src = SKILL.read_text(encoding="utf-8")
    assert src.count("**Before/after example") == 2
    first_bad = src.index("Before/after example 1 — repeated per-team round trips (BAD)")
    first_good = src.index("After — one conditional-aggregation query (GOOD)")
    second_bad = src.index("Before/after example 2 — repeated per-player round trips (BAD)")
    second_good = src.index("After — one window-function query (GOOD)")
    assert first_bad < first_good < second_bad < second_good


def test_interpretation_skill_examples_use_grouped_and_window_sql():
    src = SKILL.read_text(encoding="utf-8")
    for snippet in (
        "WHERE team_id = :team_a",
        "WHERE team_id = :team_b",
        "WHERE team_id IN (:team_a, :team_b)",
        "SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) AS wins",
        "GROUP BY team_id;",
        "WHERE player_id = :player_a",
        "WHERE player_id = :player_b",
        "WHERE player_id IN (:player_a, :player_b)",
        "WITH scoped_rows AS",
        "ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY season)",
    ):
        assert snippet in src
