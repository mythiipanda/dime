from pathlib import Path


def test_spatial_skill_documents_shot_grain_table_facts():
    text = Path("backend/analyst/skills/shot-diet-and-spatial/SKILL.md").read_text()
    assert "where shot-location data lives" in text
    assert "silver_hist_shots" in text
    assert "shot_distance" in text
    assert "season totals" in text
    assert "silver_zone_splits" in text


def test_lineups_skill_documents_group_shape_and_measure_multiplex():
    text = Path("backend/analyst/skills/lineups-and-rotations/SKILL.md").read_text()
    assert "Lineup table shape" in text or "lineup table shape" in text
    assert "lineup_id`" in text or "lineup_id," in text
    assert "MEASURE='advanced'" in text
    assert "silver_hist_lineups" in text
