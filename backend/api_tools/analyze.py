"""
Handles fetching NBA player dashboard statistics for analysis.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
import json
from typing import Dict, Any, Optional, Union, Tuple
import pandas as pd
from nba_api.stats.endpoints import playerdashboardbyyearoveryear
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, LeagueID
from ..config import settings
from ..core.errors import Errors
from .utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from ..utils.validation import _validate_season_format
from ..utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Cache Directory Setup ---
PLAYER_ANALYSIS_CSV_DIR = get_cache_dir("player_analysis")

# --- Helper Functions for CSV Caching ---
def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file.

    Args:
        df: DataFrame to save
        file_path: Path to save the CSV file
    """
    try:
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)

def _get_csv_path_for_player_analysis(
    player_id: int,
    season: str,
    season_type: str,
    per_mode: str,
    league_id: str
) -> str:
    """
    Generates a file path for saving player analysis DataFrame as CSV.

    Args:
        player_id: Player ID
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        per_mode: The per mode (e.g., 'PerGame', 'Totals')
        league_id: The league ID

    Returns:
        Path to the CSV file
    """
    # Clean season type and per mode for filename
    clean_season_type = season_type.replace(" ", "_").lower()
    clean_per_mode = per_mode.replace(" ", "_").lower()

    filename = f"player_analysis_{player_id}_{season}_{clean_season_type}_{clean_per_mode}_{league_id}.csv"
    return get_cache_file_path(filename, "player_analysis")

# Module-level constants for validation
_ANALYZE_VALID_SEASON_TYPES = {SeasonTypeAllStar.regular, SeasonTypeAllStar.playoffs, SeasonTypeAllStar.preseason} # Endpoint uses season_type_playoffs
_ANALYZE_VALID_PER_MODES = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
_ANALYZE_VALID_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}

def analyze_player_stats_logic(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches a player's overall dashboard statistics for a specified season and season type
    using the `PlayerDashboardByYearOverYear` endpoint. While the endpoint name suggests
    year-over-year data, this function primarily processes and returns the 'OverallPlayerDashboard'
    dataset, which represents the player's performance for the single specified season.
    Provides DataFrame output capabilities.

    Args:
        player_name: The full name of the player to analyze (e.g., "LeBron James").
        season: The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                Defaults to `CURRENT_SEASON` from config.
        season_type: The type of season. Valid values from `SeasonTypeAllStar`
                     (e.g., "Regular Season", "Playoffs", "Pre Season", "All Star").
                     Defaults to "Regular Season".
        per_mode: The statistical mode. Valid values from `PerModeDetailed`
                  (e.g., "PerGame", "Totals", "Per36", "Per100Possessions").
                  Defaults to "PerGame".
        league_id: The league ID. Valid values from `LeagueID` (e.g., "00" for NBA).
                   Defaults to "00" (NBA).
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string containing the player's overall dashboard statistics for the specified season.
                 Expected dictionary structure passed to format_response:
                 {
                     "player_name": str,
                     "player_id": int,
                     "season": str,
                     "season_type": str,
                     "per_mode": str,
                     "league_id": str,
                     "overall_dashboard_stats": { // Stats from OverallPlayerDashboard
                         "GROUP_SET": str, // e.g., "Overall"
                         "PLAYER_ID": int,
                         "PLAYER_NAME": str,
                         "GP": int, "W": int, "L": int, "W_PCT": float, "MIN": float,
                         "FGM": float, "FGA": float, "FG_PCT": float,
                         "FG3M": float, "FG3A": float, "FG3_PCT": float,
                         "FTM": float, "FTA": float, "FT_PCT": float,
                         "OREB": float, "DREB": float, "REB": float, "AST": float, "TOV": float,
                         "STL": float, "BLK": float, "BLKA": float, "PF": float, "PFD": float,
                         "PTS": float, "PLUS_MINUS": float,
                         "NBA_FANTASY_PTS": Optional[float], "DD2": Optional[int], "TD3": Optional[int],
                         // Other fields like GP_RANK, W_RANK, etc., might be present
                         ...
                     }
                 }
                 Returns {"overall_dashboard_stats": {}} if no data is found for the player and criteria.
                 Or an {'error': 'Error message'} object if a critical issue occurs.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing analyze_player_stats_logic for: {player_name}, Season: {season}, PerMode: {per_mode}, return_dataframe: {return_dataframe}")

    # Store DataFrames if requested
    dataframes = {}

    if not season or not _validate_season_format(season):
        error_response = format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if season_type not in _ANALYZE_VALID_SEASON_TYPES:
        error_response = format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_ANALYZE_VALID_SEASON_TYPES)[:3])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if per_mode not in _ANALYZE_VALID_PER_MODES:
        error_response = format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_ANALYZE_VALID_PER_MODES)[:5])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    if league_id not in _ANALYZE_VALID_LEAGUE_IDS:
        error_response = format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_ANALYZE_VALID_LEAGUE_IDS)[:3])))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playerdashboardbyyearoveryear for ID: {player_id} ({player_actual_name}), Season: {season}")
        try:
            player_stats_endpoint = playerdashboardbyyearoveryear.PlayerDashboardByYearOverYear(
                player_id=player_id, season=season, season_type_playoffs=season_type, # API uses season_type_playoffs
                per_mode_detailed=per_mode, league_id_nullable=league_id, timeout=settings.DEFAULT_TIMEOUT_SECONDS # Changed
            )
            logger.debug(f"playerdashboardbyyearoveryear API call successful for {player_actual_name}")
        except Exception as api_error:
            logger.error(f"API error fetching analysis stats for {player_actual_name}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_ANALYSIS_API.format(identifier=player_actual_name, error=str(api_error)) # Changed name to identifier
            error_response = format_response(error=error_msg)
            if return_dataframe:
                return error_response, dataframes
            return error_response

        overall_stats_df = player_stats_endpoint.overall_player_dashboard.get_data_frame()
        overall_stats_dict = _process_dataframe(overall_stats_df, single_row=True)

        if overall_stats_dict is None:
            if overall_stats_df.empty:
                logger.warning(f"No overall dashboard stats found for player {player_actual_name} ({season}).")
                empty_response = {
                    "player_name": player_actual_name, "player_id": player_id,
                    "season": season, "season_type": season_type, "per_mode": per_mode,
                    "league_id": league_id, "overall_dashboard_stats": {}
                }

                if return_dataframe:
                    return format_response(empty_response), dataframes
                return format_response(empty_response)
            else:
                logger.error(f"DataFrame processing failed for analysis stats of {player_actual_name} ({season}).")
                error_msg = Errors.PLAYER_ANALYSIS_PROCESSING.format(identifier=player_actual_name) # Changed name to identifier
                error_response = format_response(error=error_msg)
                if return_dataframe:
                    return error_response, dataframes
                return error_response

        response_payload = {
            "player_name": player_actual_name, "player_id": player_id,
            "season": season, "season_type": season_type, "per_mode": per_mode,
            "league_id": league_id, "overall_dashboard_stats": overall_stats_dict or {}
        }

        # Store DataFrame if requested
        if return_dataframe:
            dataframes["overall_dashboard"] = overall_stats_df

            # Save to CSV if not empty
            if not overall_stats_df.empty:
                csv_path = _get_csv_path_for_player_analysis(
                    player_id=player_id,
                    season=season,
                    season_type=season_type,
                    per_mode=per_mode,
                    league_id=league_id
                )
                _save_dataframe_to_csv(overall_stats_df, csv_path)

                # Add relative path to response
                relative_path = get_relative_cache_path(
                    os.path.basename(csv_path),
                    "player_analysis"
                )

                response_payload["dataframe_info"] = {
                    "message": "Player analysis data has been converted to DataFrame and saved as CSV file",
                    "dataframes": {
                        "overall_dashboard": {
                            "shape": list(overall_stats_df.shape),
                            "columns": overall_stats_df.columns.tolist(),
                            "csv_path": relative_path
                        }
                    }
                }

        logger.info(f"analyze_player_stats_logic completed for {player_actual_name}")

        if return_dataframe:
            return format_response(response_payload), dataframes
        return format_response(response_payload)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in analyze_player_stats_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, dataframes
        return error_response
    except ValueError as e:
        logger.warning(f"ValueError (e.g., empty player name) in analyze_player_stats_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, dataframes
        return error_response
    except Exception as e:
        logger.critical(f"Unexpected error analyzing stats for player '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_ANALYSIS_UNEXPECTED.format(identifier=player_name, error=str(e))
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, dataframes
        return error_response