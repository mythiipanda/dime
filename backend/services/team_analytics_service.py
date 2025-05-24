"""
Enhanced Team Analytics Service
Provides comprehensive team analytics using league-wide data for efficiency.
"""

import logging
import json
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from api_tools.comprehensive_analytics import analytics_engine
from api_tools.team_player_dashboard import fetch_team_player_dashboard_logic
from api_tools.team_game_logs import fetch_team_game_logs_logic
from api_tools.team_dash_lineups import fetch_team_lineups_logic

logger = logging.getLogger(__name__)

class TeamAnalyticsService:
    """
    Enhanced team analytics service that provides comprehensive team data
    using efficient league-wide data loading.
    """

    def __init__(self, team_id: int, season: str = settings.CURRENT_NBA_SEASON):
        self.team_id = team_id
        self.season = season
        self.team_data = {}
        self.players_data = []
        self.schedule_data = []
        self.lineups_data = []

    async def load_team_comprehensive_data(self) -> Dict[str, Any]:
        """
        Load comprehensive team data efficiently using league data and specific team endpoints.
        """
        try:
            logger.info(f"Loading comprehensive data for team {self.team_id}, season {self.season}")

            # Ensure league data is loaded
            await analytics_engine.load_league_data()

            # Get team data from league data
            self.team_data = self._extract_team_from_league_data()

            # Get team-specific data that requires individual API calls
            team_players_result = await self._load_team_players()
            schedule_result = await self._load_team_schedule()
            lineups_result = await self._load_team_lineups()

            # Calculate advanced team metrics
            advanced_metrics = self._calculate_team_advanced_metrics()

            return {
                'team_id': self.team_id,
                'season': self.season,
                'team_info': self.team_data,
                'players': self.players_data,
                'schedule': self.schedule_data,
                'lineups': self.lineups_data,
                'advanced_metrics': advanced_metrics,
                'data_status': {
                    'team_players': team_players_result,
                    'schedule': schedule_result,
                    'lineups': lineups_result
                }
            }

        except Exception as e:
            logger.error(f"Error loading comprehensive team data: {e}", exc_info=True)
            return {
                'error': str(e),
                'team_id': self.team_id,
                'season': self.season
            }

    def _extract_team_from_league_data(self) -> Dict[str, Any]:
        """Extract team data from loaded league data."""
        try:
            teams = analytics_engine._get_team_list()
            for team in teams:
                if team.get('TEAM_ID') == self.team_id:
                    return team
            return {}
        except Exception as e:
            logger.error(f"Error extracting team data: {e}")
            return {}

    async def _load_team_players(self) -> str:
        """Load team players data."""
        try:
            # Get team players with per-game stats
            result = await fetch_team_player_dashboard_logic(
                team_id=str(self.team_id),
                season=self.season,
                per_mode="PerGame"
            )

            if isinstance(result, str):
                data = json.loads(result)
            else:
                data = result

            # Extract players data
            if 'data_sets' in data and 'OverallTeamDashboard' in data['data_sets']:
                self.players_data = data['data_sets']['OverallTeamDashboard']

            # Enhance with advanced metrics from league data
            self._enhance_players_with_advanced_metrics()

            return 'success'

        except Exception as e:
            logger.error(f"Error loading team players: {e}")
            return f'error: {str(e)}'

    async def _load_team_schedule(self) -> str:
        """Load team schedule/game log."""
        try:
            result = await fetch_team_game_logs_logic(
                team_id=str(self.team_id),
                season=self.season
            )

            if isinstance(result, str):
                data = json.loads(result)
            else:
                data = result

            # Extract schedule data
            if 'data_sets' in data and 'TeamGameLogs' in data['data_sets']:
                self.schedule_data = data['data_sets']['TeamGameLogs']

            return 'success'

        except Exception as e:
            logger.error(f"Error loading team schedule: {e}")
            return f'error: {str(e)}'

    async def _load_team_lineups(self) -> str:
        """Load team lineups data."""
        try:
            result = await fetch_team_lineups_logic(
                team_id=str(self.team_id),
                season=self.season
            )

            if isinstance(result, str):
                data = json.loads(result)
            else:
                data = result

            # Extract lineups data
            if 'data_sets' in data and 'Lineups' in data['data_sets']:
                self.lineups_data = data['data_sets']['Lineups']

            return 'success'

        except Exception as e:
            logger.error(f"Error loading team lineups: {e}")
            return f'error: {str(e)}'

    def _enhance_players_with_advanced_metrics(self):
        """Enhance player data with advanced metrics from league data."""
        try:
            for player in self.players_data:
                player_id = player.get('PLAYER_ID')
                if player_id:
                    # Get advanced metrics from analytics engine
                    advanced_metrics = analytics_engine.calculate_advanced_player_metrics(player_id)

                    # Add advanced metrics to player data
                    if 'error' not in advanced_metrics:
                        player['advanced_metrics'] = advanced_metrics

        except Exception as e:
            logger.error(f"Error enhancing players with advanced metrics: {e}")

    def _calculate_team_advanced_metrics(self) -> Dict[str, Any]:
        """Calculate advanced team metrics."""
        try:
            metrics = {}

            # Team record and basic stats
            if self.team_data:
                metrics['basic_stats'] = {
                    'wins': self.team_data.get('W', 0),
                    'losses': self.team_data.get('L', 0),
                    'win_pct': self.team_data.get('W_PCT', 0),
                    'ppg': self.team_data.get('PTS', 0),
                    'opp_ppg': self.team_data.get('OPP_PTS', 0),
                    'net_rating': self.team_data.get('NET_RATING', 0),
                    'off_rating': self.team_data.get('OFF_RATING', 0),
                    'def_rating': self.team_data.get('DEF_RATING', 0),
                    'pace': self.team_data.get('PACE', 0)
                }

            # Schedule analysis
            if self.schedule_data:
                metrics['schedule_analysis'] = self._analyze_schedule()

            # Player contributions
            if self.players_data:
                metrics['player_contributions'] = self._analyze_player_contributions()

            # Lineup analysis
            if self.lineups_data:
                metrics['lineup_analysis'] = self._analyze_lineups()

            # League rankings
            metrics['league_rankings'] = self._calculate_league_rankings()

            return metrics

        except Exception as e:
            logger.error(f"Error calculating team advanced metrics: {e}")
            return {'error': str(e)}

    def _analyze_schedule(self) -> Dict[str, Any]:
        """Analyze team schedule and performance trends."""
        try:
            if not self.schedule_data:
                return {}

            # Recent performance (last 10 games)
            recent_games = self.schedule_data[:10] if len(self.schedule_data) >= 10 else self.schedule_data
            recent_wins = sum(1 for game in recent_games if game.get('WL') == 'W')

            # Home vs Away performance
            home_games = [g for g in self.schedule_data if '@' not in g.get('MATCHUP', '')]
            away_games = [g for g in self.schedule_data if '@' in g.get('MATCHUP', '')]

            home_wins = sum(1 for game in home_games if game.get('WL') == 'W')
            away_wins = sum(1 for game in away_games if game.get('WL') == 'W')

            # Scoring trends
            points_scored = [game.get('PTS', 0) for game in self.schedule_data if game.get('PTS')]
            points_allowed = [game.get('OPP_PTS', 0) for game in self.schedule_data if game.get('OPP_PTS')]

            return {
                'recent_record': f"{recent_wins}-{len(recent_games) - recent_wins}",
                'home_record': f"{home_wins}-{len(home_games) - home_wins}" if home_games else "0-0",
                'away_record': f"{away_wins}-{len(away_games) - away_wins}" if away_games else "0-0",
                'avg_points_scored': np.mean(points_scored) if points_scored else 0,
                'avg_points_allowed': np.mean(points_allowed) if points_allowed else 0,
                'total_games': len(self.schedule_data)
            }

        except Exception as e:
            logger.error(f"Error analyzing schedule: {e}")
            return {}

    def _analyze_player_contributions(self) -> Dict[str, Any]:
        """Analyze player contributions and roles."""
        try:
            if not self.players_data:
                return {}

            # Sort players by minutes played
            sorted_players = sorted(self.players_data, key=lambda x: x.get('MIN', 0), reverse=True)

            # Top scorers, rebounders, assisters
            top_scorer = max(self.players_data, key=lambda x: x.get('PTS', 0), default={})
            top_rebounder = max(self.players_data, key=lambda x: x.get('REB', 0), default={})
            top_assister = max(self.players_data, key=lambda x: x.get('AST', 0), default={})

            # Rotation analysis
            starters = sorted_players[:5] if len(sorted_players) >= 5 else sorted_players
            bench = sorted_players[5:12] if len(sorted_players) > 5 else []

            return {
                'top_scorer': {
                    'name': top_scorer.get('PLAYER_NAME', ''),
                    'ppg': top_scorer.get('PTS', 0)
                },
                'top_rebounder': {
                    'name': top_rebounder.get('PLAYER_NAME', ''),
                    'rpg': top_rebounder.get('REB', 0)
                },
                'top_assister': {
                    'name': top_assister.get('PLAYER_NAME', ''),
                    'apg': top_assister.get('AST', 0)
                },
                'rotation_size': len([p for p in self.players_data if p.get('MIN', 0) >= 10]),
                'starters_mpg': np.mean([p.get('MIN', 0) for p in starters]) if starters else 0,
                'bench_production': sum(p.get('PTS', 0) for p in bench) if bench else 0
            }

        except Exception as e:
            logger.error(f"Error analyzing player contributions: {e}")
            return {}

    def _analyze_lineups(self) -> Dict[str, Any]:
        """Analyze team lineups performance."""
        try:
            if not self.lineups_data:
                return {}

            # Sort lineups by minutes played
            sorted_lineups = sorted(self.lineups_data, key=lambda x: x.get('MIN', 0), reverse=True)

            # Best and worst lineups by net rating
            best_lineup = max(self.lineups_data, key=lambda x: x.get('NET_RATING', -999), default={})
            worst_lineup = min(self.lineups_data, key=lambda x: x.get('NET_RATING', 999), default={})

            # Most used lineup
            most_used = sorted_lineups[0] if sorted_lineups else {}

            return {
                'total_lineups': len(self.lineups_data),
                'most_used_lineup': {
                    'players': most_used.get('GROUP_NAME', ''),
                    'minutes': most_used.get('MIN', 0),
                    'net_rating': most_used.get('NET_RATING', 0)
                },
                'best_lineup': {
                    'players': best_lineup.get('GROUP_NAME', ''),
                    'net_rating': best_lineup.get('NET_RATING', 0),
                    'minutes': best_lineup.get('MIN', 0)
                },
                'worst_lineup': {
                    'players': worst_lineup.get('GROUP_NAME', ''),
                    'net_rating': worst_lineup.get('NET_RATING', 0),
                    'minutes': worst_lineup.get('MIN', 0)
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing lineups: {e}")
            return {}

    def _calculate_league_rankings(self) -> Dict[str, Any]:
        """Calculate team's league rankings in various categories."""
        try:
            all_teams = analytics_engine._get_team_list()
            if not all_teams or not self.team_data:
                return {}

            rankings = {}

            # Key stats to rank
            stat_categories = {
                'PTS': 'points_per_game',
                'OPP_PTS': 'opp_points_per_game',
                'NET_RATING': 'net_rating',
                'OFF_RATING': 'offensive_rating',
                'DEF_RATING': 'defensive_rating',
                'PACE': 'pace',
                'W_PCT': 'win_percentage'
            }

            for stat, name in stat_categories.items():
                if stat in self.team_data:
                    team_value = self.team_data[stat]

                    # For defensive rating and opponent points, lower is better
                    if stat in ['DEF_RATING', 'OPP_PTS']:
                        better_teams = [t for t in all_teams if t.get(stat, 999) < team_value]
                    else:
                        better_teams = [t for t in all_teams if t.get(stat, 0) > team_value]

                    rank = len(better_teams) + 1
                    rankings[name] = {
                        'rank': rank,
                        'value': team_value,
                        'total_teams': len(all_teams)
                    }

            return rankings

        except Exception as e:
            logger.error(f"Error calculating league rankings: {e}")
            return {}

# Service instance
async def get_team_comprehensive_analytics(team_id: int, season: str = settings.CURRENT_NBA_SEASON) -> Dict[str, Any]:
    """
    Get comprehensive analytics for a specific team.
    """
    service = TeamAnalyticsService(team_id, season)
    return await service.load_team_comprehensive_data()
