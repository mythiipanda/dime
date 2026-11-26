from pathlib import Path


def test_lineups_skill_has_single_pass_pattern():
    text = Path("backend/analyst/skills/lineups-and-rotations/SKILL.md").read_text()
    assert "Single-pass lineup screens" in text
    assert "silver_hist_lineups" in text
    assert "ORDER BY net_rating DESC" in text
    assert "never enumerate" in text


def test_player_eval_skill_has_single_pass_aging():
    text = Path("backend/analyst/skills/player-evaluation/SKILL.md").read_text()
    assert "Single-pass aging curves" in text
    assert "silver_hist_player_seasons" in text
    assert "GROUP BY age" in text


def test_historical_skill_has_multi_season_single_pass():
    text = Path("backend/analyst/skills/historical-grain-and-time/SKILL.md").read_text()
    assert "Multi-season assembly is one pass" in text
    assert "silver_hist_shots" in text
    assert "GROUP BY _season" in text
