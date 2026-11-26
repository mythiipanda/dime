from pathlib import Path


def test_spatial_skill_routes_zone_needs_to_shot_grain_tables():
    text = Path("backend/analyst/skills/shot-diet-and-spatial/SKILL.md").read_text()
    assert "Route the data need to the right table first" in text
    assert "silver_hist_shots" in text
    assert "season totals only" in text
    assert "DEFENDING team" in text


def test_lineups_skill_documents_group_shape_and_measure_multiplex():
    text = Path("backend/analyst/skills/lineups-and-rotations/SKILL.md").read_text()
    assert "Lineup table shape" in text
    assert "lineup_id`" in text or "lineup_id," in text
    assert "MEASURE='advanced'" in text
    assert "silver_hist_lineups" in text
