"""
Comprehensive NBA Analytics Engine
Combines multiple data sources to provide advanced analytics similar to dunksandthrees.com, craftednba.com, etc.
"""

import logging
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple, Union
import pandas as pd
import numpy as np
from functools import lru_cache
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from core.errors import Errors
from api_tools.utils import format_response
from api_tools.league_dash_player_stats import fetch_league_player_stats_logic
from api_tools.league_dash_team_stats import fetch_league_team_stats_logic
from api_tools.player_estimated_metrics import fetch_player_estimated_metrics_logic
from api_tools.team_estimated_metrics import fetch_team_estimated_metrics_logic
from utils.path_utils import get_cache_dir, get_cache_file_path

logger = logging.getLogger(__name__)

# Cache directory for comprehensive analytics
COMPREHENSIVE_ANALYTICS_CSV_DIR = get_cache_dir("comprehensive_analytics")

class AdvancedAnalyticsEngine:
    """
    Advanced analytics engine that combines multiple NBA data sources
    to create comprehensive player and team evaluations.
    """

    def __init__(self, season: str = settings.CURRENT_NBA_SEASON):
        self.season = season
        self.league_averages = {}
        self.player_data = {}
        self.team_data = {}
        self.estimated_metrics = {}

    async def load_league_data(self) -> Dict[str, Any]:
        """
        Load comprehensive league-wide data for efficient processing.
        This reduces API calls by fetching all data at once.
        """
        try:
            logger.info(f"Loading comprehensive league data for season {self.season}")

            # Fetch all league data in parallel
            tasks = [
                # Basic player stats
                asyncio.to_thread(fetch_league_player_stats_logic,
                                season=self.season, measure_type="Base", per_mode="PerGame"),
                # Advanced player stats
                asyncio.to_thread(fetch_league_player_stats_logic,
                                season=self.season, measure_type="Advanced", per_mode="PerGame"),
                # Player estimated metrics
                asyncio.to_thread(fetch_player_estimated_metrics_logic,
                                season=self.season),
                # Team stats
                asyncio.to_thread(fetch_league_team_stats_logic,
                                season=self.season, measure_type="Advanced", per_mode="PerGame"),
                # Team estimated metrics
                asyncio.to_thread(fetch_team_estimated_metrics_logic,
                                season=self.season)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            basic_players_json, advanced_players_json, player_metrics_json, team_stats_json, team_metrics_json = results

            # Parse JSON responses
            basic_players = json.loads(basic_players_json) if isinstance(basic_players_json, str) else basic_players_json
            advanced_players = json.loads(advanced_players_json) if isinstance(advanced_players_json, str) else advanced_players_json
            player_metrics = json.loads(player_metrics_json) if isinstance(player_metrics_json, str) else player_metrics_json
            team_stats = json.loads(team_stats_json) if isinstance(team_stats_json, str) else team_stats_json
            team_metrics = json.loads(team_metrics_json) if isinstance(team_metrics_json, str) else team_metrics_json

            # Store processed data
            self.player_data = {
                'basic': basic_players,
                'advanced': advanced_players,
                'estimated_metrics': player_metrics
            }

            self.team_data = {
                'stats': team_stats,
                'estimated_metrics': team_metrics
            }

            # Calculate league averages
            self._calculate_league_averages()

            logger.info("Successfully loaded comprehensive league data")
            return {
                'status': 'success',
                'season': self.season,
                'players_loaded': len(self._get_player_list()),
                'teams_loaded': len(self._get_team_list()),
                'league_averages': self.league_averages
            }

        except Exception as e:
            logger.error(f"Error loading league data: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e)
            }

    def _calculate_league_averages(self):
        """Calculate league averages for various metrics."""
        try:
            # Extract basic player stats for league averages
            basic_data = self.player_data.get('basic', {})
            if 'data_sets' in basic_data and 'LeagueDashPlayerStats' in basic_data['data_sets']:
                players = basic_data['data_sets']['LeagueDashPlayerStats']

                if players:
                    # Calculate averages for key metrics
                    df = pd.DataFrame(players)

                    # Filter for players with meaningful minutes (>= 10 MPG)
                    if 'MIN' in df.columns:
                        qualified_players = df[df['MIN'] >= 10.0]
                    else:
                        qualified_players = df

                    if not qualified_players.empty:
                        self.league_averages = {
                            'PPG': qualified_players['PTS'].mean() if 'PTS' in qualified_players.columns else 0,
                            'RPG': qualified_players['REB'].mean() if 'REB' in qualified_players.columns else 0,
                            'APG': qualified_players['AST'].mean() if 'AST' in qualified_players.columns else 0,
                            'FG_PCT': qualified_players['FG_PCT'].mean() if 'FG_PCT' in qualified_players.columns else 0,
                            'FG3_PCT': qualified_players['FG3_PCT'].mean() if 'FG3_PCT' in qualified_players.columns else 0,
                            'FT_PCT': qualified_players['FT_PCT'].mean() if 'FT_PCT' in qualified_players.columns else 0,
                            'MPG': qualified_players['MIN'].mean() if 'MIN' in qualified_players.columns else 0,
                            'qualified_players': len(qualified_players)
                        }

                        logger.info(f"Calculated league averages for {len(qualified_players)} qualified players")

        except Exception as e:
            logger.error(f"Error calculating league averages: {e}", exc_info=True)
            # Set default league averages
            self.league_averages = {
                'PPG': 11.2, 'RPG': 4.1, 'APG': 2.4,
                'FG_PCT': 0.462, 'FG3_PCT': 0.349, 'FT_PCT': 0.783,
                'MPG': 20.5, 'qualified_players': 0
            }

    def _get_player_list(self) -> List[Dict[str, Any]]:
        """Get list of all players from loaded data."""
        try:
            basic_data = self.player_data.get('basic', {})
            if 'data_sets' in basic_data and 'LeagueDashPlayerStats' in basic_data['data_sets']:
                return basic_data['data_sets']['LeagueDashPlayerStats']
            return []
        except:
            return []

    def _get_team_list(self) -> List[Dict[str, Any]]:
        """Get list of all teams from loaded data."""
        try:
            team_data = self.team_data.get('stats', {})
            if 'data_sets' in team_data and 'LeagueDashTeamStats' in team_data['data_sets']:
                return team_data['data_sets']['LeagueDashTeamStats']
            return []
        except:
            return []

    def calculate_advanced_player_metrics(self, player_id: int) -> Dict[str, Any]:
        """
        Calculate advanced metrics for a specific player.
        Similar to EPM, RAPTOR, and other advanced metrics.
        """
        try:
            # Find player in basic and advanced stats
            basic_stats = self._find_player_stats(player_id, 'basic')
            advanced_stats = self._find_player_stats(player_id, 'advanced')
            estimated_metrics = self._find_player_estimated_metrics(player_id)

            if not basic_stats:
                return {'error': f'Player {player_id} not found in basic stats'}

            # Calculate custom advanced metrics
            metrics = {}

            # Basic efficiency metrics
            if basic_stats.get('MIN', 0) > 0:
                # Points per minute
                metrics['PPM'] = basic_stats.get('PTS', 0) / basic_stats.get('MIN', 1)
                # Rebounds per minute
                metrics['RPM'] = basic_stats.get('REB', 0) / basic_stats.get('MIN', 1)
                # Assists per minute
                metrics['APM'] = basic_stats.get('AST', 0) / basic_stats.get('MIN', 1)

            # True Shooting Percentage
            pts = basic_stats.get('PTS', 0)
            fga = basic_stats.get('FGA', 0)
            fta = basic_stats.get('FTA', 0)
            if fga > 0 or fta > 0:
                metrics['TS_PCT'] = pts / (2 * (fga + 0.44 * fta)) if (fga + 0.44 * fta) > 0 else 0

            # Effective Field Goal Percentage
            fgm = basic_stats.get('FGM', 0)
            fg3m = basic_stats.get('FG3M', 0)
            if fga > 0:
                metrics['EFG_PCT'] = (fgm + 0.5 * fg3m) / fga

            # Usage Rate (simplified)
            if advanced_stats and 'USG_PCT' in advanced_stats:
                metrics['USG_PCT'] = advanced_stats['USG_PCT']

            # Player Impact Estimate (PIE) - simplified version
            if advanced_stats and 'PIE' in advanced_stats:
                metrics['PIE'] = advanced_stats['PIE']

            # Add estimated metrics if available
            if estimated_metrics:
                metrics.update({
                    'E_OFF_RATING': estimated_metrics.get('E_OFF_RATING', 0),
                    'E_DEF_RATING': estimated_metrics.get('E_DEF_RATING', 0),
                    'E_NET_RATING': estimated_metrics.get('E_NET_RATING', 0),
                    'E_PACE': estimated_metrics.get('E_PACE', 0),
                    'E_USG_PCT': estimated_metrics.get('E_USG_PCT', 0)
                })

            # Calculate percentile rankings vs league
            metrics['percentiles'] = self._calculate_percentiles(basic_stats, advanced_stats)

            return metrics

        except Exception as e:
            logger.error(f"Error calculating advanced metrics for player {player_id}: {e}", exc_info=True)
            return {'error': str(e)}

    def _find_player_stats(self, player_id: int, stat_type: str) -> Optional[Dict[str, Any]]:
        """Find player stats in the loaded data."""
        try:
            data = self.player_data.get(stat_type, {})
            if 'data_sets' in data and 'LeagueDashPlayerStats' in data['data_sets']:
                players = data['data_sets']['LeagueDashPlayerStats']
                for player in players:
                    if player.get('PLAYER_ID') == player_id:
                        return player
            return None
        except:
            return None

    def _find_player_estimated_metrics(self, player_id: int) -> Optional[Dict[str, Any]]:
        """Find player estimated metrics in the loaded data."""
        try:
            data = self.player_data.get('estimated_metrics', {})
            if 'player_estimated_metrics' in data:
                players = data['player_estimated_metrics']
                for player in players:
                    if player.get('PLAYER_ID') == player_id:
                        return player
            return None
        except:
            return None

    def _calculate_percentiles(self, basic_stats: Dict[str, Any], advanced_stats: Optional[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate percentile rankings for key stats."""
        try:
            all_players = self._get_player_list()
            if not all_players:
                return {}

            # Filter for qualified players (>= 10 MPG)
            qualified_players = [p for p in all_players if p.get('MIN', 0) >= 10.0]

            if not qualified_players:
                return {}

            percentiles = {}

            # Key stats to calculate percentiles for
            key_stats = ['PTS', 'REB', 'AST', 'FG_PCT', 'FG3_PCT', 'FT_PCT', 'STL', 'BLK', 'TOV']

            for stat in key_stats:
                if stat in basic_stats:
                    player_value = basic_stats[stat]
                    all_values = [p.get(stat, 0) for p in qualified_players if p.get(stat) is not None]

                    if all_values and player_value is not None:
                        # Calculate percentile (higher is better for most stats, except TOV)
                        if stat == 'TOV':
                            # For turnovers, lower is better
                            percentile = (sum(1 for v in all_values if v > player_value) / len(all_values)) * 100
                        else:
                            # For other stats, higher is better
                            percentile = (sum(1 for v in all_values if v < player_value) / len(all_values)) * 100

                        percentiles[f'{stat}_PERCENTILE'] = round(percentile, 1)

            return percentiles

        except Exception as e:
            logger.error(f"Error calculating percentiles: {e}", exc_info=True)
            return {}

# Global analytics engine instance
analytics_engine = AdvancedAnalyticsEngine()

async def get_comprehensive_league_data(season: str = settings.CURRENT_NBA_SEASON) -> Dict[str, Any]:
    """
    Get comprehensive league data for efficient team/player page loading.
    """
    global analytics_engine

    # Update season if different
    if analytics_engine.season != season:
        analytics_engine = AdvancedAnalyticsEngine(season)

    # Load data if not already loaded
    result = await analytics_engine.load_league_data()

    return {
        'season': season,
        'data_status': result,
        'league_averages': analytics_engine.league_averages,
        'players_count': len(analytics_engine._get_player_list()),
        'teams_count': len(analytics_engine._get_team_list())
    }

async def get_player_advanced_analytics(player_id: int, season: str = settings.CURRENT_NBA_SEASON) -> Dict[str, Any]:
    """
    Get advanced analytics for a specific player.
    """
    global analytics_engine

    # Ensure data is loaded
    if analytics_engine.season != season or not analytics_engine.player_data:
        await analytics_engine.load_league_data()

    # Calculate advanced metrics
    metrics = analytics_engine.calculate_advanced_player_metrics(player_id)

    return {
        'player_id': player_id,
        'season': season,
        'advanced_metrics': metrics,
        'league_averages': analytics_engine.league_averages
    }
