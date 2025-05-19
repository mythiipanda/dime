"""
Shot chart module for NBA player shot analysis.
Provides both JSON and DataFrame outputs with CSV caching.
"""

import logging
import json
import os
from typing import Dict, List, Optional, Any, Union, Tuple
import pandas as pd
import numpy as np
from nba_api.stats.endpoints import shotchartdetail
from nba_api.stats.static import players, teams
from .utils import retry_on_timeout, format_response, get_player_id_from_name
from ..config import settings
from ..core.errors import Errors
from ..utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Cache Directory Setup ---
SHOT_CHARTS_CSV_DIR = get_cache_dir("shot_charts")

def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file, creating the directory if it doesn't exist.

    Args:
        df: The DataFrame to save
        file_path: The path to save the CSV file
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Save DataFrame to CSV
        df.to_csv(file_path, index=False)
        logger.debug(f"Saved DataFrame to {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to {file_path}: {e}", exc_info=True)

def _get_csv_path_for_shot_chart(player_id: int, season: str, season_type: str) -> str:
    """
    Generates a file path for saving shot chart data as CSV.

    Args:
        player_id: The player ID
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')

    Returns:
        Path to the CSV file
    """
    # Clean season type for filename
    clean_season_type = season_type.replace(" ", "_").lower()

    # Handle None season
    season_str = season if season else "current"

    filename = f"player_{player_id}_shots_{season_str}_{clean_season_type}.csv"
    return get_cache_file_path(filename, "shot_charts")

def fetch_player_shot_chart(
    player_name: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    context_measure: str = "FGA",
    last_n_games: int = 0,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches shot chart data for a specified player.
    Provides DataFrame output capabilities.

    Args:
        player_name (str): The full name of the player to analyze.
        season (str, optional): The NBA season in format YYYY-YY (e.g., "2023-24").
            If None, uses the current season.
        season_type (str): The type of season. Options: "Regular Season", "Playoffs", "Pre Season", "All Star".
        context_measure (str): The statistical measure. Options: "FGA", "FGM", "FG_PCT", etc.
        last_n_games (int): Number of most recent games to include (0 for all games).
        return_dataframe (bool, optional): Whether to return DataFrames along with the JSON response.
                                          Defaults to False.

    Returns:
        If return_dataframe=False:
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
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    try:
        # Initialize dataframes dictionary if returning DataFrames
        dataframes = {}

        # Get player ID
        player_id_result = get_player_id_from_name(player_name)
        if isinstance(player_id_result, dict) and 'error' in player_id_result:
            error_response = format_response(error=player_id_result['error'])
            if return_dataframe:
                return error_response, dataframes
            return error_response

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
            error_response = format_response(error=f"No shot data found for {player_name}")
            if return_dataframe:
                return error_response, dataframes
            return error_response

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

        # If DataFrame output is requested, save DataFrames and return them
        if return_dataframe:
            # Add shots DataFrame
            shots_df_processed = pd.DataFrame(shots)
            dataframes["shots"] = shots_df_processed

            # Add zones DataFrame
            zones_df = pd.DataFrame(zones)
            dataframes["zones"] = zones_df

            # Add raw shot data
            dataframes["raw_shots"] = shots_df

            # Add league averages
            dataframes["league_averages"] = league_avg_df

            # Save DataFrames to CSV
            if not shots_df_processed.empty:
                shots_csv_path = _get_csv_path_for_shot_chart(player_id, season, season_type)
                _save_dataframe_to_csv(shots_df_processed, shots_csv_path)

                # Add DataFrame metadata to the response
                result["dataframe_info"] = {
                    "message": "Shot chart data has been converted to DataFrames and saved as CSV files",
                    "dataframes": {
                        "shots": {
                            "shape": list(shots_df_processed.shape),
                            "columns": shots_df_processed.columns.tolist(),
                            "csv_path": get_relative_cache_path(os.path.basename(shots_csv_path), "shot_charts")
                        },
                        "zones": {
                            "shape": list(zones_df.shape),
                            "columns": zones_df.columns.tolist()
                        },
                        "raw_shots": {
                            "shape": list(shots_df.shape),
                            "columns": shots_df.columns.tolist()
                        },
                        "league_averages": {
                            "shape": list(league_avg_df.shape),
                            "columns": league_avg_df.columns.tolist()
                        }
                    }
                }

            return format_response(result), dataframes

        # Return just the JSON response if DataFrames are not requested
        return format_response(result)

    except Exception as e:
        logger.error(f"Error in fetch_player_shot_chart for {player_name}: {str(e)}", exc_info=True)
        error_response = format_response(error=f"Failed to fetch shot chart for {player_name}: {str(e)}")
        if return_dataframe:
            return error_response, {}
        return error_response
