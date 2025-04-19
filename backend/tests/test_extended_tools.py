import json
import pytest
import tools


def test_get_season_matchups(monkeypatch):
    # Arrange
    expected = json.dumps({"season": "2024-25", "matchups": []})
    monkeypatch.setattr(tools, 'fetch_league_season_matchups_logic', lambda *args, **kwargs: expected)

    # Act
    result = tools.get_season_matchups('1', '2', season='2024-25', season_type='Regular Season')

    # Assert
    assert isinstance(result, str)
    data = json.loads(result)
    assert data['season'] == '2024-25'
    assert 'matchups' in data


def test_get_matchups_rollup(monkeypatch):
    # Arrange
    expected = json.dumps({"season": "2024-25", "rollup": []})
    monkeypatch.setattr(tools, 'fetch_matchups_rollup_logic', lambda *args, **kwargs: expected)

    # Act
    result = tools.get_matchups_rollup('3', season='2024-25', season_type='Playoffs')

    # Assert
    assert isinstance(result, str)
    data = json.loads(result)
    assert data['season'] == '2024-25'
    assert 'rollup' in data


def test_get_synergy_play_types(monkeypatch):
    # Arrange
    expected = json.dumps({"data": []})
    monkeypatch.setattr(tools, 'fetch_synergy_play_types_logic', lambda *args, **kwargs: expected)

    # Act
    result = tools.get_synergy_play_types(
        league_id='00', per_mode='PerGame', player_or_team_abbreviation='P',
        season_type='Regular Season', season='2024-25', play_type='Isolation', type_grouping='General'
    )

    # Assert
    assert isinstance(result, str)
    data = json.loads(result)
    assert 'data' in data


def test_get_player_analysis(monkeypatch):
    # Arrange
    expected = json.dumps({"player_name": "LeBron James", "overall_dashboard_stats": []})
    monkeypatch.setattr(tools, 'analyze_player_stats_logic', lambda *args, **kwargs: expected)

    # Act
    result = tools.get_player_analysis(
        'LeBron James', season='2024-25', season_type='Playoffs', per_mode='PerGame', league_id='00'
    )

    # Assert
    assert isinstance(result, str)
    data = json.loads(result)
    assert data['player_name'] == 'LeBron James'
    assert 'overall_dashboard_stats' in data
