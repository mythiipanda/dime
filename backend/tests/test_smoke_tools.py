import pytest

from backend.tools import (
    get_season_matchups,
    get_matchups_rollup,
    get_synergy_play_types,
    get_player_analysis
)

# Smoke tests to ensure tools run without crashing
def test_smoke_season_matchups():
    result = get_season_matchups('2544', '201939', '2023-24', 'Regular Season')
    assert result, "get_season_matchups returned empty or falsy"


def test_smoke_matchups_rollup():
    result = get_matchups_rollup('2544', '2023-24', 'Regular Season')
    assert result, "get_matchups_rollup returned empty or falsy"


def test_smoke_synergy_play_types():
    # Using team-level synergy play types as example
    result = get_synergy_play_types('00', 'Totals', 'T', 'Regular Season', '2023-24')
    assert result, "get_synergy_play_types returned empty or falsy"


def test_smoke_player_analysis():
    result = get_player_analysis('LeBron James', '2023-24', 'Regular Season', 'PerGame', '00')
    assert result, "get_player_analysis returned empty or falsy"
