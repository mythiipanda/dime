from pathlib import Path

SKILL = (Path(__file__).resolve().parents[1]
         / "analyst" / "skills" / "statistical-modeling" / "SKILL.md").read_text()


def test_correlation_recipe_present():
    assert "CORR(x, y)" in SKILL
    assert "near-zero coefficient is a valid answer" in SKILL
    assert "Never force the expected sign" in SKILL


def test_regression_recipe_present():
    assert "statistics.mean" in SKILL
    assert "residuals" in SKILL
    assert "not proof of coaching or chemistry" in SKILL


def test_aging_curve_recipe_present():
    assert "silver_hist_player_seasons" in SKILL
    assert "HAVING COUNT(*) >= 30" in SKILL
    assert "usg_pct` is a fraction" in SKILL
    assert "peak age" in SKILL


def test_recipes_use_qualified_cohorts():
    assert "min >= 20" in SKILL
    assert "gp >= 41" in SKILL
