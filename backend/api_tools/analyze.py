import logging
import json
from typing import Dict, Any, Optional
import pandas as pd # Not strictly used now but kept for potential future use with other dataframes from endpoint
from nba_api.stats.endpoints import playerdashboardbyyearoveryear
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, LeagueID
from backend.config import CURRENT_SEASON, DEFAULT_TIMEOUT, Errors
from backend.api_tools.utils import (
    _process_dataframe,
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError,
    _validate_season_format,
)

logger = logging.getLogger(__name__)

def analyze_player_stats_logic(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches a player's overall dashboard statistics for a specified season and season type
    using the `PlayerDashboardByYearOverYear` endpoint. While the endpoint name suggests
    year-over-year data, this function primarily processes and returns the 'OverallPlayerDashboard'
    dataset, which represents the player's performance for the single specified season.

    Args:
        player_name (str): The full name of the player to analyze (e.g., "LeBron James").
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
                                Defaults to `CURRENT_SEASON` from config.
        season_type (str, optional): The type of season. Valid values from `SeasonTypeAllStar`
                                     (e.g., "Regular Season", "Playoffs", "Pre Season", "All Star").
                                     Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode. Valid values from `PerModeDetailed`
                                  (e.g., "PerGame", "Totals", "Per36", "Per100Possessions").
                                  Defaults to "PerGame".
        league_id (str, optional): The league ID. Valid values from `LeagueID` (e.g., "00" for NBA).
                                   Defaults to "00" (NBA).

    Returns:
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
    """
    logger.info(f"Executing analyze_player_stats_logic for: {player_name}, Season: {season}, PerMode: {per_mode}")

    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        return format_response(error=Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(VALID_SEASON_TYPES)))

    VALID_PER_MODES = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
    if per_mode not in VALID_PER_MODES:
        return format_response(error=Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(VALID_PER_MODES)))

    VALID_LEAGUE_IDS = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}
    if league_id not in VALID_LEAGUE_IDS:
        return format_response(error=Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(VALID_LEAGUE_IDS)))

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playerdashboardbyyearoveryear for ID: {player_id} ({player_actual_name}), Season: {season}")
        try:
            player_stats_endpoint = playerdashboardbyyearoveryear.PlayerDashboardByYearOverYear(
                player_id=player_id, season=season, season_type_playoffs=season_type, # API uses season_type_playoffs
                per_mode_detailed=per_mode, league_id_nullable=league_id, timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"playerdashboardbyyearoveryear API call successful for {player_actual_name}")
        except Exception as api_error:
            logger.error(f"API error fetching analysis stats for {player_actual_name}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_ANALYSIS_API.format(name=player_actual_name, error=str(api_error))
            return format_response(error=error_msg)

        overall_stats_df = player_stats_endpoint.overall_player_dashboard.get_data_frame()
        overall_stats_dict = _process_dataframe(overall_stats_df, single_row=True)

        if overall_stats_dict is None:
            if overall_stats_df.empty:
                logger.warning(f"No overall dashboard stats found for player {player_actual_name} ({season}).")
                return format_response({
                    "player_name": player_actual_name, "player_id": player_id,
                    "season": season, "season_type": season_type, "per_mode": per_mode,
                    "league_id": league_id, "overall_dashboard_stats": {}
                })
            else:
                logger.error(f"DataFrame processing failed for analysis stats of {player_actual_name} ({season}).")
                error_msg = Errors.PLAYER_ANALYSIS_PROCESSING.format(name=player_actual_name)
                return format_response(error=error_msg)

        response_payload = {
            "player_name": player_actual_name, "player_id": player_id,
            "season": season, "season_type": season_type, "per_mode": per_mode,
            "league_id": league_id, "overall_dashboard_stats": overall_stats_dict or {}
        }
        logger.info(f"analyze_player_stats_logic completed for {player_actual_name}")
        return format_response(response_payload)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in analyze_player_stats_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e: # Catches empty player name from find_player_id_or_error
        logger.warning(f"ValueError (e.g., empty player name) in analyze_player_stats_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error analyzing stats for player '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_ANALYSIS_UNEXPECTED.format(name=player_name, error=str(e))
        return format_response(error=error_msg)