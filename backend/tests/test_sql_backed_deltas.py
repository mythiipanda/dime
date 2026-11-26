from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_skill_teaches_sql_backed_deltas():
    src = (ROOT / "backend/analyst/skills/factual-accuracy-and-exactness/SKILL.md").read_text()
    assert "inside `sql_exec` itself" in src
    assert "never by mental arithmetic" in src
    assert "does not appear verbatim in a tool result" in src


def test_skill_presubmission_covers_derived_figures():
    src = (ROOT / "backend/analyst/skills/factual-accuracy-and-exactness/SKILL.md").read_text()
    assert "Every derived figure" in src
    assert "recompute it inside sql_exec before submitting" in src
