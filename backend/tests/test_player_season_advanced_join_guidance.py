from pathlib import Path


def test_warehouse_guide_documents_player_season_scope():
    text = Path("backend/analyst/skills/warehouse-guide/SKILL.md").read_text()
    assert "silver_player_season" in text
    assert "PPG" in text


def test_warehouse_guide_routes_efficiency_metrics_to_advanced():
    text = Path("backend/analyst/skills/warehouse-guide/SKILL.md").read_text()
    assert "TS_PCT" in text
    assert "USG_PCT" in text
    assert "silver_advanced" in text
    assert "PLAYER_ID" in text and "_season" in text


def test_warehouse_guide_names_efficiency_screen_join():
    text = Path("backend/analyst/skills/warehouse-guide/SKILL.md").read_text()
    assert "Scoring-efficiency screens" in text
