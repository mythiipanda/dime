from shared.tools.league.leaders import get_leaders


def test_description_names_per_game_rate_categories():
    d = get_leaders.description
    for cat in ("PPG", "RPG", "APG"):
        assert cat in d
    assert "TOTALS" in d
