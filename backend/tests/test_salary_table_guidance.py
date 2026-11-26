from pathlib import Path


def test_warehouse_guide_documents_silver_salaries():
    text = Path("backend/analyst/skills/warehouse-guide/SKILL.md").read_text()
    assert "silver_salaries" in text
    assert "SALARY_2025_26" in text
    assert "trade matching-band math" in text


def test_hist_seasons_redirects_salary_asks():
    text = Path("backend/analyst/skills/warehouse-guide/SKILL.md").read_text()
    assert "no salary columns" in text


def test_canonical_map_names_salary_columns():
    text = Path("backend/analyst/runtime.ts").read_text()
    assert "SALARY_2025_26" in text
    assert "never silver_hist_player_seasons" in text
