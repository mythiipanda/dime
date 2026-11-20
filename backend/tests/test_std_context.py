import duckdb
import pytest

from shared import store
from shared.tools._core import season_to_date_meta
from shared.tools import player, team


HIST_COLS = ("team_id BIGINT, team_abbreviation VARCHAR, game_id VARCHAR, "
             "game_date VARCHAR, matchup VARCHAR, wl VARCHAR, min DOUBLE, "
             "fgm DOUBLE, fga DOUBLE, fg_pct DOUBLE, fg3m DOUBLE, fg3a DOUBLE, "
             "fg3_pct DOUBLE, ftm DOUBLE, fta DOUBLE, ft_pct DOUBLE, "
             "oreb DOUBLE, dreb DOUBLE, reb DOUBLE, ast DOUBLE, stl DOUBLE, "
             "blk DOUBLE, tov DOUBLE, pf DOUBLE, pts DOUBLE, "
             "season_type VARCHAR, _season VARCHAR")


@pytest.fixture
def warehouse(tmp_path, monkeypatch):
    path = tmp_path / 'std.duckdb'
    monkeypatch.setattr(store, 'DB_PATH', path)
    monkeypatch.setattr(store, 'LOCK_PATH', tmp_path / '.write.lock')
    monkeypatch.setattr(player, 'last_completed_season', lambda: '2025-26')
    monkeypatch.setattr(team, 'last_completed_season', lambda: '2025-26')
    con = duckdb.connect(str(path))
    con.execute(f"CREATE TABLE silver_hist_gamelogs ({HIST_COLS})")
    for i in range(15):
        con.execute(
            "INSERT INTO silver_hist_gamelogs VALUES (1610612738, 'BOS', ?, '2026-11-01', 'BOS vs. NYK', 'W', 48, 40, 80, .5, 10, 30, .33, 10, 12, .8, 10, 30, 40, 20, 5, 3, 15, 18, 110, 'regular-season', '2026-27')",
            [f'002{i:05d}'])
    for i in range(16):
        con.execute(
            "INSERT INTO silver_hist_gamelogs VALUES (1610612752, 'NYK', ?, '2026-11-02', 'NYK vs. BOS', 'W', 48, 40, 80, .5, 10, 30, .33, 10, 12, .8, 10, 30, 40, 20, 5, 3, 15, 18, 108, 'regular-season', '2026-27')",
            [f'003{i:05d}'])
    for i in range(82):
        con.execute(
            "INSERT INTO silver_hist_gamelogs VALUES (1610612738, 'BOS', ?, '2025-10-20', 'BOS vs. NYK', ?, 48, 40, 80, .5, 10, 30, .33, 10, 12, .8, 10, 30, 40, 20, 5, 3, 15, 18, 110, 'regular-season', '2025-26')",
            [f'001{i:05d}', 'W' if i < 60 else 'L'])
    con.execute(
        "CREATE TABLE silver_player_season (PLAYER_ID BIGINT, PLAYER VARCHAR, TEAM VARCHAR, AGE DOUBLE, GP BIGINT, MPG DOUBLE, PPG DOUBLE, RPG DOUBLE, APG DOUBLE, SPG DOUBLE, BPG DOUBLE, FG_PCT DOUBLE, FG3_PCT DOUBLE, FT_PCT DOUBLE, TS_PCT DOUBLE, _season VARCHAR)")
    con.execute(
        "INSERT INTO silver_player_season VALUES (1, 'Example Star', 'BOS', 27, 15, 36, 30.5, 8.1, 5.2, 1.1, .5, .48, .38, .9, .62, '2026-27')")
    con.execute(
        "INSERT INTO silver_player_season VALUES (1, 'Example Star', 'BOS', 26, 74, 35, 26.8, 7.9, 4.9, 1.0, .4, .47, .37, .88, .60, '2025-26')")
    con.execute(
        "INSERT INTO silver_player_season VALUES (2, 'Hurt Example', 'BOS', 28, 15, 33, 24.1, 6.5, 4.0, .9, .3, .46, .35, .85, .58, '2025-26')")
    con.close()
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    yield path
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()


def test_std_meta_flags_early_season_with_baseline(warehouse):
    meta = season_to_date_meta('2026-27', 15)
    assert meta['games_played'] == 15
    assert meta['league_games_played_baseline'] == 16
    assert meta['small_sample'] is True
    assert meta['small_sample_reason'] == 'early in the season'


def test_std_meta_flags_behind_baseline(warehouse, monkeypatch):
    import shared.tools._core as core
    monkeypatch.setattr(core, 'league_games_played_baseline', lambda season: 60)
    meta = season_to_date_meta('2026-27', 30)
    assert meta['small_sample'] is True
    assert meta['small_sample_reason'] == 'well under the league games-played baseline'


def test_std_meta_prior_full_season_and_static_season_skipped(warehouse):
    meta = season_to_date_meta('2026-27', 15, {'season': '2025-26', 'ppg': 26.8})
    assert meta['prior_full_season']['season'] == '2025-26'
    meta = season_to_date_meta('2024-25', 78)
    assert 'league_games_played_baseline' not in meta


def test_season_averages_carries_std_context(warehouse):
    result = player.get_season_averages.invoke({'player_id': 1, 'season': '2026-27'})
    assert result['ok']
    std = result['meta']['season_to_date']
    assert std['games_played'] == 15
    assert std['league_games_played_baseline'] == 16
    assert std['small_sample'] is True
    prior = std['prior_full_season']
    assert prior['season'] == '2025-26'
    assert prior['games_played'] == 74
    assert prior['ppg'] == 26.8


def test_team_season_summary_carries_std_context(warehouse):
    result = team.get_team_season_summary.invoke(
        {'team_id': 'BOS', 'season': '2026-27', 'period_scope': 'regular_season'})
    assert result['ok']
    std = result['meta']['season_to_date']
    assert std['games_played'] == 15
    assert std['league_games_played_baseline'] == 16
    assert std['small_sample'] is True
    prior = std['prior_full_season']
    assert prior['season'] == '2025-26'
    assert prior['games_played'] == 82
    assert prior['wins'] == 60


def test_static_season_has_no_std_context(warehouse):
    result = team.get_team_season_summary.invoke(
        {'team_id': 'BOS', 'season': '2025-26', 'period_scope': 'regular_season'})
    assert result['ok']
    assert 'season_to_date' not in result['meta']
    result = player.get_season_averages.invoke({'player_id': 1, 'season': '2025-26'})
    assert result['ok']
    assert 'season_to_date' not in result['meta']


def test_completed_season_low_gp_still_flagged(warehouse):
    result = player.get_season_averages.invoke({'player_id': 2, 'season': '2025-26'})
    assert result['ok']
    std = result['meta']['season_to_date']
    assert std['games_played'] == 15
    assert std['small_sample'] is True
    assert std['small_sample_reason'] == 'well under the league games-played baseline'
