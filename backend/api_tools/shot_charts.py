"""
Shot chart module for NBA player shot analysis.
"""

import logging
import json
from typing import Dict, List, Optional, Any, Union
import pandas as pd
import numpy as np
from nba_api.stats.endpoints import shotchartdetail
from nba_api.stats.static import players, teams
from .utils import retry_on_timeout, format_response, get_player_id_from_name
from ..config import settings
from ..core.errors import Errors

logger = logging.getLogger(__name__)

def fetch_player_shot_chart(
    player_name: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    context_measure: str = "FGA",
    last_n_games: int = 0
) -> str:
    """
    Fetches shot chart data for a specified player.

    Args:
        player_name (str): The full name of the player to analyze.
        season (str, optional): The NBA season in format YYYY-YY (e.g., "2023-24").
            If None, uses the current season.
        season_type (str): The type of season. Options: "Regular Season", "Playoffs", "Pre Season", "All Star".
        context_measure (str): The statistical measure. Options: "FGA", "FGM", "FG_PCT", etc.
        last_n_games (int): Number of most recent games to include (0 for all games).

    Returns:
        str: JSON string containing shot chart data and zone analysis.
             Expected structure:
             {
                 "player_name": str,
                 "player_id": int,
                 "team_name": str,
                 "team_id": int,
                 "season": str,
                 "season_type": str,
                 "shots": [
                     {
                         "x": float,  // X coordinate on court
                         "y": float,  // Y coordinate on court
                         "made": bool,  // Whether shot was made
                         "value": int,  // 2 or 3 points
                         "shot_type": str,  // Shot type description
                         "shot_zone": str,  // Shot zone description
                         "distance": float,  // Distance in feet
                         "game_date": str,  // Date of game
                         "period": int,  // Quarter/period
                     },
                     // ... other shots
                 ],
                 "zones": [
                     {
                         "zone": str,  // Zone name
                         "attempts": int,  // Field goal attempts
                         "made": int,  // Field goals made
                         "percentage": float,  // FG percentage
                         "leaguePercentage": float,  // League average FG percentage
                         "relativePercentage": float,  // Difference from league average
                     },
                     // ... other zones
                 ]
             }
             Or an {'error': 'Error message'} object if an issue occurs.
    """
    try:
        # Get player ID
        player_id_result = get_player_id_from_name(player_name)
        if isinstance(player_id_result, dict) and 'error' in player_id_result:
            return format_response(error=player_id_result['error'])

        player_id = player_id_result

        # Get team ID (use 0 if we can't determine it)
        team_id = 0
        team_name = ""

        # Find the player's current team
        all_players = players.get_players()
        for p in all_players:
            if p['id'] == player_id:
                player_name = p['full_name']  # Use the official name from the API
                break

        # Use the NBA API to get shot chart data
        def fetch_shot_chart():
            return shotchartdetail.ShotChartDetail(
                player_id=player_id,
                team_id=team_id,
                season_nullable=season,
                season_type_all_star=season_type,
                context_measure_simple=context_measure,
                last_n_games=last_n_games,
                league_id='00'
            )

        shot_chart_data = retry_on_timeout(fetch_shot_chart)

        # Process shot data
        shots_df = shot_chart_data.get_data_frames()[0]
        league_avg_df = shot_chart_data.get_data_frames()[1]

        if shots_df.empty:
            return format_response(error=f"No shot data found for {player_name}")

        # Get team info from the first shot
        if team_id == 0 and not shots_df.empty:
            team_id = shots_df.iloc[0]['TEAM_ID']
            team_name = shots_df.iloc[0]['TEAM_NAME']

        # Transform shot data to our format
        shots = []
        for _, row in shots_df.iterrows():
            shot = {
                'x': float(row['LOC_X']),
                'y': float(row['LOC_Y']),
                'made': bool(row['SHOT_MADE_FLAG']),
                'value': 3 if row['SHOT_TYPE'] == '3PT Field Goal' else 2,
                'shot_type': row['ACTION_TYPE'],
                'shot_zone': f"{row['SHOT_ZONE_BASIC']} - {row['SHOT_ZONE_AREA']}",
                'distance': float(row['SHOT_DISTANCE']),
                'game_date': row['GAME_DATE'],
                'period': int(row['PERIOD']),
            }
            shots.append(shot)

        # Process zone data
        zones = []
        for zone_basic in league_avg_df['SHOT_ZONE_BASIC'].unique():
            zone_data = league_avg_df[league_avg_df['SHOT_ZONE_BASIC'] == zone_basic]

            # Player's data for this zone
            player_zone_data = shots_df[shots_df['SHOT_ZONE_BASIC'] == zone_basic]
            player_attempts = len(player_zone_data)
            player_made = player_zone_data['SHOT_MADE_FLAG'].sum()
            player_pct = player_made / player_attempts if player_attempts > 0 else 0

            # League average for this zone
            league_attempts = zone_data['FGA'].sum()
            league_made = zone_data['FGM'].sum()
            league_pct = league_made / league_attempts if league_attempts > 0 else 0

            # Calculate relative percentage
            relative_pct = player_pct - league_pct

            zone = {
                'zone': zone_basic,
                'attempts': int(player_attempts),
                'made': int(player_made),
                'percentage': float(player_pct),
                'leaguePercentage': float(league_pct),
                'relativePercentage': float(relative_pct)
            }
            zones.append(zone)

        result = {
            'player_name': player_name,
            'player_id': player_id,
            'team_name': team_name,
            'team_id': team_id,
            'season': season,
            'season_type': season_type,
            'shots': shots,
            'zones': zones
        }

        return format_response(result)

    except Exception as e:
        logger.error(f"Error in fetch_player_shot_chart for {player_name}: {str(e)}", exc_info=True)
        return format_response(error=f"Failed to fetch shot chart for {player_name}: {str(e)}")
